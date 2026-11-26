// Connexion GMAO (Supabase Auth), partagee par les pages de l'application.
// - Adresse et mot de passe demandes une seule fois par appareil ; le mot de passe n'est jamais enregistre.
// - Les appels a la base partent ensuite avec le jeton de la personne connectee (renouvele automatiquement).
// - ETAPE DE TRANSITION : la base accepte encore les acces sans connexion. En cas de probleme de connexion, la
//   saisie reste possible comme avant. Ce repli sera retire avant de fermer la base.
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

  // Jeton valable, ou null (on continue alors comme avant la connexion).
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

  // La base repond 401 ou 403 ; l'espace de fichiers repond souvent 400 avec le code 403 dans le message.
  function refusee(rep, adresse) {
    if (rep.status === 401 || rep.status === 403) return Promise.resolve(true);
    if (rep.status !== 400 || adresse.indexOf(URL_BASE + '/storage/') !== 0) return Promise.resolve(false);
    return rep.clone().json().then(
      function (c) { var code = String(c && c.statusCode); return code === '401' || code === '403'; },
      function () { return false; });
  }

  window.fetch = function (cible, options) {
    var adresse = typeof cible === 'string' ? cible : (cible && cible.url) || '';
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
      if (!t) return envoyer(cible, options);
      return avec(t).then(function (rep) {
        return refusee(rep, adresse).then(function (non) {
          if (!non) return rep;
          // refuse avec ce jeton (rien n'a ete ecrit) : jeton neuf, sinon acces comme avant (transition)
          return jeton(true).then(function (t2) {
            return (t2 ? avec(t2) : envoyer(cible, options)).then(function (r2) {
              return refusee(r2, adresse).then(function (encore) {
                if (!encore) return r2;
                console.warn('GMAO : acces refuse avec la session, nouvel essai sans connexion');
                return envoyer(cible, options);
              });
            });
          });
        });
      });
    });
  };

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
    var plusTard = element('button', 'display:none;width:100%;margin-top:12px;padding:10px;border:none;background:none;color:#666;font-size:13px;text-decoration:underline', 'Continuer sans me connecter cette fois');
    plusTard.type = 'button';
    plusTard.onclick = function () { voile.remove(); };
    form.appendChild(erreur); form.appendChild(bouton); form.appendChild(plusTard);
    form.onsubmit = function (ev) {
      ev.preventDefault();
      bouton.disabled = true; bouton.textContent = 'Connexion…'; erreur.textContent = '';
      connecter(email.value, passe.value)
        .then(function () { passe.value = ''; voile.remove(); afficherEtat(); })
        .catch(function (e) {
          erreur.textContent = e.message;
          bouton.disabled = false; bouton.textContent = 'Se connecter';
          plusTard.style.display = 'block';
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

  function demarrer() {
    if (ecranApplication) return;
    afficherEtat();
    if (!session()) afficherConnexion('');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
  else demarrer();

  window.GMAOSession = { session: session, jeton: jeton, connecter: connecter, deconnecter: deconnecter };
})();
