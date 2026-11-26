// Connexion GMAO (Supabase Auth), partagee par les pages de l'application.
// - Adresse et mot de passe demandes une seule fois par appareil ; le mot de passe n'est jamais enregistre.
// - Les appels a la base partent ensuite avec le jeton de la personne connectee (renouvele automatiquement).
// - La base refuse tout acces sans connexion : une page non connectee demande l'adresse et le mot de passe.
// - Les documents sont prives : les liens enregistres (« .../object/public/... ») sont remplaces au moment de
//   l'affichage ou de l'ouverture par des liens temporaires. La base garde les liens d'origine.
(function () {
  'use strict';
  if (window.GMAOSession) return;

  var URL_BASE = 'https://jbiphusmneoccarwkucq.supabase.co';
  var CLE_PUBLIQUE = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpiaXBodXNtbmVvY2NhcndrdWNxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3MTI3ODIsImV4cCI6MjA4OTI4ODc4Mn0.meNA4EocaV5J8_9RL929w3fUOwFI5exFHnXr2nKRHjM';
  var RANGEMENT = 'gmao_session';
  var envoyer = window.fetch.bind(window);
  var renouvellement = null;
  var ecranApplication = !!(document.currentScript && document.currentScript.getAttribute('data-ecran') === 'application');

  function lire() {
    try { return JSON.parse(localStorage.getItem(RANGEMENT)) || null; } catch (e) { return null; }
  }
  function enregistrer(r, email) {
    var s = {
      access_token: r.access_token,
      refresh_token: r.refresh_token,
      expire: Math.floor(Date.now() / 1000) + (r.expires_in || 3600),
      email: (r.user && r.user.email) || email || ''
    };
    try { localStorage.setItem(RANGEMENT, JSON.stringify(s)); } catch (e) { /* navigation privee */ }
    memoire = s;
    return s;
  }
  function oublier() {
    memoire = null;
    try { localStorage.removeItem(RANGEMENT); } catch (e) { /* rien */ }
  }
  var memoire = lire();
  function session() { return lire() || memoire; }

  function demanderJeton(type, corps) {
    return envoyer(URL_BASE + '/auth/v1/token?grant_type=' + type, {
      method: 'POST',
      headers: { apikey: CLE_PUBLIQUE, 'Content-Type': 'application/json' },
      body: JSON.stringify(corps)
    });
  }

  // Jeton valable, ou null (pas de session, ou renouvellement impossible).
  function jeton(forcer) {
    var s = session();
    if (!s) return Promise.resolve(null);
    if (!forcer && s.expire - 60 > Date.now() / 1000) return Promise.resolve(s.access_token);
    if (!renouvellement) {
      renouvellement = demanderJeton('refresh_token', { refresh_token: s.refresh_token })
        .then(function (rep) {
          if (rep.ok) return rep.json().then(function (r) { return enregistrer(r, s.email).access_token; });
          if (rep.status === 400 || rep.status === 401 || rep.status === 403) {
            // session refusee (compte modifie, mot de passe change...) : il faudra se reconnecter
            var actuelle = lire();
            if (actuelle && actuelle.refresh_token !== s.refresh_token) return actuelle.access_token;
            oublier();
            if (ecranApplication) location.reload();
            else afficherConnexion('Votre session a expiré, reconnectez-vous.');
          }
          return null;
        })
        .catch(function () { return null; })           // pas de reseau : on reessaiera au prochain appel
        .then(function (t) { renouvellement = null; return t; });
    }
    return renouvellement;
  }

  // Le jeton est-il refuse (expire, revoque) ? Un refus de droits ordinaire n'est pas concerne.
  function jetonRefuse(rep, adresse) {
    if (rep.status === 401) return Promise.resolve(true);
    // l'espace de fichiers signale un jeton perime par une erreur 400 qui cite « jwt »
    if (rep.status !== 400 || adresse.indexOf(URL_BASE + '/storage/') !== 0) return Promise.resolve(false);
    return rep.clone().text().then(function (t) { return /jwt/i.test(t); }, function () { return false; });
  }

  window.fetch = function (cible, options) {
    var adresse = typeof cible === 'string' ? cible : (cible && cible.url) || '';
    // lecture d'un document par le code (piece jointe, annexe d'un bail) : par le chemin reserve aux connectes
    var methode = String((options && options.method) || 'GET').toUpperCase();
    if (fichier(adresse) && (methode === 'GET' || methode === 'HEAD')) {
      adresse = URL_BASE + '/storage/v1/object/authenticated/' + adresse.slice(DOCUMENTS.length);
      cible = adresse;
      var entetes = new Headers((options && options.headers) || {});
      entetes.set('apikey', CLE_PUBLIQUE);
      options = Object.assign({}, options, { headers: entetes });
    }
    if (adresse.indexOf(URL_BASE + '/rest/') !== 0 && adresse.indexOf(URL_BASE + '/storage/') !== 0) {
      return envoyer(cible, options);
    }
    function avec(t) {
      var o = Object.assign({}, options);
      var h = new Headers(o.headers || {});
      h.set('Authorization', 'Bearer ' + t);
      o.headers = h;
      return envoyer(cible, o);
    }
    return jeton(false).then(function (t) {
      if (!t) {
        // session presente mais jeton impossible a renouveler : une erreur vaut mieux qu'une liste vide
        if (session()) throw new TypeError('Connexion indisponible, réessayez.');
        return envoyer(cible, options);
      }
      return avec(t).then(function (rep) {
        return jetonRefuse(rep, adresse).then(function (oui) {
          if (!oui) return rep;
          // rien n'a ete ecrit : un seul nouvel essai avec un jeton neuf
          return jeton(true).then(function (t2) { return t2 ? avec(t2) : rep; });
        });
      });
    });
  };

  // ---------------------------------------------------------------- documents prives
  var DOCUMENTS = URL_BASE + '/storage/v1/object/public/';
  var DUREE = 3600;      // validite d'un lien temporaire, en secondes
  var liensSignes = {};

  // « espace/chemin » d'un lien de document enregistre, sinon null
  function fichier(url) {
    if (typeof url !== 'string' || url.indexOf(DOCUMENTS) !== 0) return null;
    return url.slice(DOCUMENTS.length).split(/[?#]/)[0] || null;
  }

  // Lien temporaire (promesse) ; les autres adresses sont rendues telles quelles.
  function lien(url) {
    var chemin = fichier(url);
    if (!chemin) return Promise.resolve(url);
    var connu = liensSignes[url];
    if (connu && connu.fin > Date.now()) return connu.promesse;
    var suite = url.indexOf('?') > 0 ? url.slice(url.indexOf('?') + 1) : '';
    var promesse = window.fetch(URL_BASE + '/storage/v1/object/sign/' + chemin, {
      method: 'POST',
      headers: { apikey: CLE_PUBLIQUE, 'Content-Type': 'application/json' },
      body: JSON.stringify({ expiresIn: DUREE })
    }).then(function (rep) {
      if (!rep.ok) throw new Error('document introuvable ou non autorisé');
      return rep.json();
    }).then(function (r) {
      // « v=... » est conserve pour qu'un fichier remplace ne reste pas en memoire du navigateur
      return URL_BASE + '/storage/v1' + r.signedURL + (suite ? '&' + suite : '');
    });
    liensSignes[url] = { fin: Date.now() + (DUREE - 300) * 1000, promesse: promesse };
    promesse.catch(function () { delete liensSignes[url]; });
    return promesse;
  }

  // La fenetre est ouverte tout de suite (sinon le navigateur la bloque), puis recoit le lien temporaire.
  var ouvrirFenetre = window.open ? window.open.bind(window) : null;
  function ouvrirDocument(url, nom, reglages) {
    var fenetre = ouvrirFenetre ? ouvrirFenetre('', nom || '_blank', reglages) : null;
    lien(url).then(function (temporaire) {
      if (fenetre) fenetre.location.replace(temporaire);
      else location.assign(temporaire);
    }, function (e) {
      if (fenetre) fenetre.close();
      window.alert('Impossible d’ouvrir ce document : ' + e.message);
    });
    return fenetre;
  }
  if (ouvrirFenetre) {
    window.open = function (url, nom, reglages) {
      if (fichier(url)) return ouvrirDocument(url, nom, reglages);
      return ouvrirFenetre.apply(window, arguments);
    };
  }

  // images et apercus affiches dans la page
  var VIDE = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
  function habiller(element) {
    var source = element.getAttribute && element.getAttribute('src');
    if (!fichier(source)) return;
    element.setAttribute('src', VIDE);
    lien(source).then(function (temporaire) {
      if (element.getAttribute('src') === VIDE) element.setAttribute('src', temporaire);
    }, function () { element.setAttribute('alt', 'Document non autorisé'); });
  }
  var AFFICHES = 'img[src],iframe[src],embed[src]';
  function examiner(noeud) {
    if (noeud.nodeType !== 1) return;
    if (noeud.matches(AFFICHES)) habiller(noeud);
    Array.prototype.forEach.call(noeud.querySelectorAll(AFFICHES), habiller);
  }
  if (window.MutationObserver && document.documentElement) {
    new MutationObserver(function (changements) {
      changements.forEach(function (c) {
        if (c.type === 'attributes') habiller(c.target);
        else Array.prototype.forEach.call(c.addedNodes, examiner);
      });
    }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] });
  }
  // liens « Voir », « Ouvrir »...
  if (document.addEventListener) {
    document.addEventListener('click', function (ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
      if (!a || !fichier(a.getAttribute('href'))) return;
      ev.preventDefault();
      ouvrirDocument(a.getAttribute('href'), '_blank');
    }, true);
  }

  // Connexion avec adresse et mot de passe (formulaire d'une page ou de l'application).
  function connecter(adresse, motDePasse) {
    adresse = String(adresse || '').trim().toLowerCase();
    return demanderJeton('password', { email: adresse, password: motDePasse })
      .then(function (rep) {
        if (!rep.ok) throw new Error(rep.status === 400 ? 'Adresse ou mot de passe incorrect.' : 'Connexion refusée (erreur ' + rep.status + ').');
        return rep.json();
      })
      .then(function (r) { return enregistrer(r, adresse); })
      .catch(function (e) { throw e instanceof TypeError ? new Error('Pas de connexion internet.') : e; });
  }

  // Ferme la session de cet appareil (et la revoque chez Supabase si le reseau le permet).
  function deconnecter() {
    var s = session();
    oublier(); afficherEtat();
    if (!s) return Promise.resolve();
    return envoyer(URL_BASE + '/auth/v1/logout?scope=local', {
      method: 'POST',
      headers: { apikey: CLE_PUBLIQUE, Authorization: 'Bearer ' + s.access_token }
    }).then(function () {}, function () {});
  }

  function element(balise, style, texte) {
    var e = document.createElement(balise);
    if (style) e.style.cssText = style;
    if (texte) e.textContent = texte;
    return e;
  }

  function afficherConnexion(message) {
    if (!document.body || document.getElementById('gmao-connexion')) return;
    var voile = element('div', 'position:fixed;inset:0;z-index:100000;background:#f0f4f8;overflow:auto;padding:32px 20px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif');
    voile.id = 'gmao-connexion';
    var form = element('form', 'max-width:360px;margin:0 auto;background:#fff;border-radius:16px;padding:24px;box-shadow:0 4px 16px rgba(0,0,0,.08)');
    form.appendChild(element('div', 'font-size:22px;font-weight:700;color:#185FA5;margin-bottom:6px', 'Connexion GMAO'));
    form.appendChild(element('div', 'font-size:14px;color:#555;margin-bottom:18px', 'Demandée une seule fois sur cet appareil.'));
    var champ = 'width:100%;box-sizing:border-box;padding:12px 14px;border:1.5px solid #ddd;border-radius:10px;font-size:16px;margin:4px 0 14px';
    function saisie(libelle, type, nom, auto) {
      var l = element('label', 'display:block;font-size:13px;color:#444', libelle);
      var i = element('input', champ);
      i.type = type; i.name = nom; i.autocomplete = auto; i.required = true;
      i.setAttribute('autocapitalize', 'none');
      l.appendChild(i); form.appendChild(l);
      return i;
    }
    var email = saisie('Adresse mail', 'email', 'email', 'username');
    var passe = saisie('Mot de passe', 'password', 'password', 'current-password');
    var erreur = element('div', 'color:#C0392B;font-size:13px;min-height:18px;margin-bottom:10px', message || '');
    erreur.id = 'gmao-erreur';
    var bouton = element('button', 'width:100%;padding:15px;border:none;border-radius:12px;background:#185FA5;color:#fff;font-size:16px;font-weight:700', 'Se connecter');
    bouton.type = 'submit';
    form.appendChild(erreur); form.appendChild(bouton);
    form.onsubmit = function (ev) {
      ev.preventDefault();
      bouton.disabled = true; bouton.textContent = 'Connexion…'; erreur.textContent = '';
      connecter(email.value, passe.value)
        .then(function () { passe.value = ''; voile.remove(); afficherEtat(); habillerCompte(); })
        .catch(function (e) {
          erreur.textContent = e.message;
          bouton.disabled = false; bouton.textContent = 'Se connecter';
        });
    };
    voile.appendChild(form);
    document.body.appendChild(voile);
  }

  // Petite ligne sous le clavier PIN : qui est connecte sur cet appareil
  function afficherEtat() {
    var ecran = document.getElementById('pin-screen');
    if (!ecran) return;
    var ancien = document.getElementById('gmao-etat');
    if (ancien) ancien.remove();
    var s = session();
    var ligne = element('div', 'text-align:center;font-size:12px;color:#777;margin-top:24px');
    ligne.id = 'gmao-etat';
    ligne.appendChild(document.createTextNode(s ? 'Connecté : ' + s.email + ' · ' : 'Non connecté · '));
    var lien = element('a', 'color:#185FA5;text-decoration:underline;cursor:pointer', s ? 'se déconnecter' : 'se connecter');
    lien.onclick = function () {
      if (s && !window.confirm('Se déconnecter de cet appareil ?')) return;
      oublier(); afficherEtat(); afficherConnexion('');
    };
    ligne.appendChild(lien);
    ecran.appendChild(ligne);
  }

  // Pages mobiles : une fois connecte, le logo d'en-tete suit le compte (l'application principale gere le sien).
  function habillerCompte() {
    var images = document.querySelectorAll('img[data-logo-compte]');
    if (!images.length || !session()) return;
    var entetes = { headers: { apikey: CLE_PUBLIQUE } };
    function lireListe(chemin) {
      return window.fetch(URL_BASE + '/rest/v1/' + chemin, entetes).then(function (r) { return r.ok ? r.json() : []; });
    }
    lireListe('acces?select=utilisateur_id').then(function (a) {
      return a.length ? lireListe('users?select=role,profile&id=eq.' + a[0].utilisateur_id) : [];
    }).then(function (u) {
      if (!u.length) return;
      var logo = u[0].profile === 'dubail' ? 'logo-savadur.png'
        : (u[0].role === 'admin' || u[0].profile === 'famille_jm') ? 'logo-pauline-antoine.png' : null;
      if (!logo) return;
      Array.prototype.forEach.call(images, function (i) {
        i.style.width = 'auto'; i.style.maxWidth = '96px';
        i.src = logo;
      });
    }).catch(function () { /* le logo neutre reste */ });
  }

  function demarrer() {
    if (ecranApplication) return;
    afficherEtat();
    if (!session()) afficherConnexion('');
    else habillerCompte();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
  else demarrer();

  window.GMAOSession = { session: session, jeton: jeton, connecter: connecter, deconnecter: deconnecter, lien: lien };
})();
