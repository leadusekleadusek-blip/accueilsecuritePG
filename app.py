import os
import json
import time
import random
import requests
from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet
import qrcode

# =========================================================================
# 1. CONFIGURATION INITIALE & STYLES ADAPTATIFS
# =========================================================================

st.set_page_config(
    page_title="Accueil Sécurité — P&G Amiens",
    page_icon="🛡️",
    layout="wide"
)

st.markdown("""
    <style>
        html, body, [class*="css"] { font-family: 'Segoe UI', -apple-system, Roboto, sans-serif; }
        .main-header {
            background: linear-gradient(135deg, #003B71 0%, #005691 100%);
            padding: 20px; border-radius: 10px; color: #FFFFFF !important;
            text-align: center; margin-bottom: 25px;
        }
        .main-header h1 { color: #FFFFFF !important; margin: 0; font-size: 1.8rem; font-weight: 700; }
        .section-card {
            background-color: var(--secondary-background-color);
            border-left: 6px solid #003B71; padding: 18px 22px;
            border-radius: 6px; margin-top: 20px; margin-bottom: 20px;
        }
        .flash-popup {
            background-color: #FFF9E6; border: 3px solid #FFC107;
            padding: 25px; border-radius: 10px; margin-top: 20px; margin-bottom: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); color: #222222;
        }
        .quiz-card {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 18px; border-radius: 8px; margin-bottom: 15px;
        }
    </style>
""", unsafe_allow_html=True)

ADMIN_PASSWORD = "Casque rouge P&G26"
QUESTIONS_FILE = "questions.json"
FORMS_DIR = "pdf_generated"
os.makedirs(FORMS_DIR, exist_ok=True)

AIRTABLE_API_KEY = st.secrets.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = st.secrets.get("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = st.secrets.get("AIRTABLE_TABLE_NAME", "RegistreAccueils")

if "video_url" not in st.session_state: st.session_state.video_url = ""
if "video_started" not in st.session_state: st.session_state.video_started = False
if "reponses_flash_engins" not in st.session_state: st.session_state.reponses_flash_engins = False
if "score_flash_correct" not in st.session_state: st.session_state.score_flash_correct = 0
if "total_flash_eval" not in st.session_state: st.session_state.total_flash_eval = 0
if "flash_repondues" not in st.session_state: st.session_state.flash_repondues = set()
if "questions_flash_tirees" not in st.session_state: st.session_state.questions_flash_tirees = {}

# =========================================================================
# 2. GESTION BASE DE DONNÉES & AIRTABLE
# =========================================================================

def charger_questions():
    if not os.path.exists(QUESTIONS_FILE):
        def_q = {
            "flash": [
                {
                    "minutes": 1, "secondes": 30,
                    "banque_questions": [
                        {"texte": "La limite de vitesse sur le site est de 20km/h", "reponse": "Vrai"},
                        {"texte": "La limite de vitesse sur le site est de 30km/h", "reponse": "Faux"},
                        {"texte": "Il n'existe pas de limite de vitesse sur le site", "reponse": "Faux"}
                    ],
                    "mode_reponse": "Avec réponse attendue (Évalué)",
                    "declenche_engins": False
                }
            ],
            "general": [],
            "engins": []
        }
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(def_q, f, ensure_ascii=False, indent=4)
        return def_q
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def sauvegarder_questions(data):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def enregistrer_airtable(donnees):
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID: return False
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "records": [{
            "fields": {
                "Nom": donnees.get("nom", ""),
                "Prenom": donnees.get("prenom", ""),
                "Entreprise": donnees.get("entreprise", ""),
                "EmailResponsable": donnees.get("email", ""),
                "Mode": donnees.get("mode", ""),
                "TempsPresenceMin": donnees.get("temps_presence", 0),
                "ScoreGeneral": float(donnees.get("score_general", 0)),
                "StatutGeneral": donnees.get("statut_general", ""),
                "StatutEngins": donnees.get("statut_engins", "NON_CONCERNE"),
                "DatePassation": donnees.get("timestamp", "")
            }
        }]
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        return r.status_code == 200
    except Exception: return False

def lire_airtable():
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID: return []
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return [rec["fields"] for rec in r.json().get("records", [])]
        return []
    except Exception: return []

def generer_pdf(d):
    filepath = os.path.join(FORMS_DIR, f"Pass_Securite_{d['nom']}_{d['prenom']}.pdf")
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    header_table = Table([
        [Paragraph("<font size=22 color='#003B71'><b>P&amp;G</b></font>", styles['Normal']),
         Paragraph("<font color='#003B71' size=14><b>ATTESTATION D'ACCUEIL SÉCURITÉ SITE</b><br/><font size=9 color='#4A5568'>Procter &amp; Gamble Amiens</font></font>", styles['Normal'])]
    ], colWidths=[100, 400])
    story.append(header_table)
    story.append(Spacer(1, 15))
    
    now = datetime.now()
    exp = datetime(now.year + 1, now.month, now.day)
    
    txt = f"""
    <b>INTERVENANT :</b> {d['prenom']} {d['nom'].upper()}<br/>
    <b>ENTREPRISE :</b> {d['entreprise']}<br/>
    <b>DATE DE VALIDATION :</b> {now.strftime('%d/%m/%Y')}<br/>
    <b>EXPIRATION :</b> {exp.strftime('%d/%m/%Y')} <i>(Valable 1 an)</i><br/><br/>
    <b>STATUT SÉCURITÉ GÉNÉRAL :</b> <font color='green'><b>🟢 ACCUEIL VALIDÉ</b></font><br/>
    <b>AUTORISATION ENGINS / GRUES :</b> {d['statut_engins']}
    """
    story.append(Paragraph(txt, styles['Normal']))
    story.append(Spacer(1, 15))

    qr_img = qrcode.make(f"PG_VALIDATED|{d['nom']}|{d['prenom']}|EXP:{exp.strftime('%Y%m%d')}")
    qr_img.save("temp_qr.png")
    story.append(Image("temp_qr.png", width=90, height=90))

    doc.build(story)
    return filepath

# =========================================================================
# 3. PORTAIL INTERVENANT
# =========================================================================

st.sidebar.markdown("# **P&G Amiens**")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["🏢 Portail Intervenant", "⚙️ Espace Administrateur HSE"])

if page == "🏢 Portail Intervenant":
    st.markdown("""<div class="main-header"><h1>🛡️ Accueil Sécurité Site — Procter & Gamble Amiens</h1></div>""", unsafe_allow_html=True)
    if "step" not in st.session_state: st.session_state.step = 1

    # ÉTAPE 1 : IDENTIFICATION
    if st.session_state.step == 1:
        st.markdown('<div class="section-card"><h2>👤 Étape 1 : Identification de l\'Intervenant</h2></div>', unsafe_allow_html=True)
        with st.form("id_form"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom").upper()
                prenom = st.text_input("Prénom").capitalize()
            with col2:
                entreprise = st.text_input("Entreprise Extérieure")
                email = st.text_input("E-mail du Responsable")

            mode = st.selectbox("Mode de formation", ["DISTANCIEL (Autonome)", "SALLE (Collectif)"])
            if st.form_submit_button("Valider mes informations ➔"):
                if nom and prenom and entreprise:
                    st.session_state.user_data = {"nom": nom, "prenom": prenom, "entreprise": entreprise, "email": email, "mode": mode}
                    st.session_state.step = 2
                    st.rerun()
                else: st.error("Veuillez remplir vos informations nominatives.")

    # ÉTAPE 2 : VIDÉO BRIDÉE & POP-UP FLASH DYNAMIQUE
    elif st.session_state.step == 2:
        st.markdown('<div class="section-card"><h2>🎥 Étape 2 : Sensibilisation Vidéo & Questions-Flash</h2></div>', unsafe_allow_html=True)

        if not st.session_state.video_started:
            st.info("Cliquez sur le bouton ci-dessous pour démarrer la séance. Le chronomètre officiel sera activé.")
            if st.button("▶️ LANCER LA VIDÉO D'ACCUEIL SÉCURITÉ", type="primary"):
                st.session_state.video_started = True
                st.session_state.start_time = datetime.now()
                st.rerun()
        else:
            q_db = charger_questions()
            flash_list = q_db.get("flash", [])
            elapsed_sec = int((datetime.now() - st.session_state.start_time).total_seconds())

            # Détection d'une question-flash active non encore répondue
            flash_active_idx = None
            for idx, f in enumerate(flash_list):
                target_sec = (f.get("minutes", 0) * 60) + f.get("secondes", 0)
                if elapsed_sec >= target_sec and idx not in st.session_state.flash_repondues:
                    flash_active_idx = idx
                    break

            # SI UNE QUESTION-FLASH EST DÉCLENCHÉE : PAUSE ET POP-UP EXCLUSIF
            if flash_active_idx is not None:
                st.warning("⏸️ VIDÉO EN PAUSE — Question-Flash de vérification")
                f_active = flash_list[flash_active_idx]

                # Tirage au sort d'une question dans la banque si pas fait
                if flash_active_idx not in st.session_state.questions_flash_tirees:
                    banque = f_active.get("banque_questions", [])
                    st.session_state.questions_flash_tirees[flash_active_idx] = random.choice(banque) if banque else {"texte": "Question indisponible", "reponse": "Vrai"}

                q_selected = st.session_state.questions_flash_tirees[flash_active_idx]

                st.markdown(f'''
                    <div class="flash-popup">
                        <h3>⚡ Question-Flash ({f_active.get("minutes",0)}m{f_active.get("secondes",0)}s)</h3>
                        <p style="font-size:1.2rem; font-weight:600;">{q_selected["texte"]}</p>
                    </div>
                ''', unsafe_allow_html=True)

                ans_f = st.radio("Votre réponse :", ["Vrai", "Faux"], key=f"popup_ans_{flash_active_idx}")

                if st.button("Valider la réponse et reprendre la vidéo ▶️"):
                    if ans_f == "Vrai" and f_active.get("declenche_engins"):
                        st.session_state.reponses_flash_engins = True

                    if f_active.get("mode_reponse") == "Avec réponse attendue (Évalué)":
                        st.session_state.total_flash_eval += 1
                        if ans_f == q_selected.get("reponse"):
                            st.session_state.score_flash_correct += 1

                    st.session_state.flash_repondues.add(flash_active_idx)
                    st.rerun()

            else:
                # LECTEUR VIDÉO BRIDÉ (SANS CURSEUR NI AVANCE RAPIDE)
                v_url = st.session_state.video_url
                if v_url:
                    if "iframe" in v_url.lower() or "embed" in v_url.lower():
                        st.components.v1.html(v_url, height=450)
                    else:
                        video_html = f"""
                        <div style="position: relative; width: 100%; max-width: 800px; margin: auto;">
                            <video id="pgVideo" width="100%" autoplay style="border-radius: 8px; pointer-events: none;">
                                <source src="{v_url}" type="video/mp4">
                                Votre navigateur ne supporte pas la lecture vidéo.
                            </video>
                            <div style="position: absolute; top:0; left:0; width:100%; height:100%; z-index: 10;"></div>
                        </div>
                        <script>
                            const video = document.getElementById('pgVideo');
                            video.addEventListener('ratechange', () => {{ if (video.playbackRate !== 1.0) video.playbackRate = 1.0; }});
                            video.addEventListener('contextmenu', event => event.preventDefault());
                        </script>
                        """
                        st.components.v1.html(video_html, height=460)
                else:
                    st.info("📹 Vidéo en cours de lecture...")

                # Auto-rafraîchissement toutes les 3s pour vérifier le chrono des questions-flash
                time.sleep(3)
                st.rerun()

    # ÉTAPE 3 : QUESTIONNAIRE GÉNÉRAL & ENGINS
    elif st.session_state.step == 3:
        st.markdown('<div class="section-card"><h2>📝 Étape 3 : Questionnaire de Validation</h2></div>', unsafe_allow_html=True)

        if st.session_state.total_flash_eval > 0 and st.session_state.score_flash_correct == st.session_state.total_flash_eval:
            st.success("🌟 **Super, vous avez été très attentif pendant la vidéo !** Passons maintenant au questionnaire de validation des connaissances.")
        else:
            st.info("💡 **Veuillez rester bien attentif et concentré** pour répondre au questionnaire ci-dessous.")

        q_db = charger_questions()
        reponses_gen = {}
        st.markdown("### 📋 **Tronc Commun Général**")
        for idx, q in enumerate(q_db.get("general", [])):
            st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
            opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
            reponses_gen[idx] = st.radio(
                f"**Q{idx+1}. {q['texte']}** *(Barème : {q.get('points', 1.0)} pt)* {'*(🚨 Éliminatoire)*' if q.get('eliminatoire') else ''}", 
                opts, key=f"gen_{idx}"
            )
            st.markdown('</div>', unsafe_allow_html=True)

        reponses_eng = {}
        if st.session_state.reponses_flash_engins and len(q_db.get("engins", [])) > 0:
            st.markdown("---")
            st.markdown("### 🚜 **Module Spécifique Engins / Grues**")
            for idx, q in enumerate(q_db.get("engins", [])):
                st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
                opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                reponses_eng[idx] = st.radio(f"**Q_Engin_{idx+1}. {q['texte']}**", opts, key=f"eng_{idx}")
                st.markdown('</div>', unsafe_allow_html=True)

        if st.button("Passer à l'Émargement & Signature ➔"):
            st.session_state.reponses_gen_val = reponses_gen
            st.session_state.step = 4
            st.rerun()

    # ÉTAPE 4 : SIGNATURE & SOUMISSION
    elif st.session_state.step == 4:
        st.markdown('<div class="section-card"><h2>✍️ Étape 4 : Attestation sur l\'honneur & Validation</h2></div>', unsafe_allow_html=True)
        
        if "resultat_final" not in st.session_state:
            st.caption("Je certifie sur l'honneur être la personne réalisant cet accueil sécurité et avoir suivi la formation sans assistance.")
            canvas_result = st_canvas(stroke_width=2, stroke_color="#003B71", background_color="#FAFAFA", height=130, key="sig_canvas")

            if st.button("💾 Soumettre et Valider mon Accueil Sécurité"):
                q_db = charger_questions()
                score_gen = 0.0
                fautes_elim = 0
                
                reponses_gen = st.session_state.get("reponses_gen_val", {})
                for idx, q in enumerate(q_db.get("general", [])):
                    opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                    rep_ind = opts.index(reponses_gen[idx]) if idx in reponses_gen and reponses_gen[idx] in opts else -1
                    if rep_ind == int(q["reponse"]): score_gen += float(q.get("points", 1.0))
                    elif q.get("eliminatoire"): fautes_elim += 1

                ud = st.session_state.get("user_data", {"nom": "NOM", "prenom": "Prenom", "entreprise": "Entreprise"})
                ud["temps_presence"] = 42
                ud["score_general"] = score_gen
                ud["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if fautes_elim == 0 and score_gen >= 1.0:
                    ud["statut_general"] = "VALIDE"
                    ud["statut_engins"] = "AUTORISÉE" if st.session_state.reponses_flash_engins else "NON_CONCERNE"
                    enregistrer_airtable(ud)
                    st.session_state.resultat_final = {"status": "SUCCESS", "data": ud, "pdf": generer_pdf(ud)}
                else:
                    ud["statut_general"] = "ECHEC"
                    ud["statut_engins"] = "NON_CONCERNE"
                    enregistrer_airtable(ud)
                    st.session_state.resultat_final = {"status": "FAILURE", "data": ud}

                st.rerun()
        else:
            res = st.session_state.resultat_final
            if res.get("status") == "SUCCESS":
                st.balloons()
                st.success("🟢 ACCUEIL SÉCURITÉ VALIDÉ !")
                st.write(f"Bravo **{res['data']['prenom']} {res['data']['nom']}**, votre score final est de **{res['data']['score_general']} pt(s)**.")
                with open(res["pdf"], "rb") as f:
                    st.download_button("📄 Télécharger mon Attestation Sécurité PDF", f, file_name=os.path.basename(res["pdf"]))
            else:
                st.error("🔴 ÉCHEC DE VALIDATION DE L'ACCUEIL SÉCURITÉ")
                st.write("Veuillez contacter le service HSE P&G Amiens.")

            if st.button("Terminer et recommencer"):
                del st.session_state["resultat_final"]
                st.session_state.step = 1
                st.session_state.video_started = False
                st.rerun()

# =========================================================================
# 4. ESPACE ADMINISTRATEUR
# =========================================================================
elif page == "⚙️ Espace Administrateur HSE":
    st.markdown("""<div class="main-header"><h1>🔒 Panneau d'Administration HSE — P&G Amiens</h1></div>""", unsafe_allow_html=True)
    pwd = st.sidebar.text_input("Code secret Administrateur", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.sidebar.success("Accès Administrateur Autorisé")
        admin_section = st.sidebar.radio("📌 Section Admin :", ["⚙️ 1. Vidéo Cloud", "⚡ 2. Banques Questions-Flash", "📋 3. Questionnaire Général", "🚜 4. Questionnaire Engins", "📊 5. Registre Airtable"])
        q_data = charger_questions()

        if "⚙️ 1." in admin_section:
            st.subheader("1. Vidéo Cloud Entreprise (Stream / SharePoint / Direct MP4)")
            v_input = st.text_area("Lien Web Direct (.mp4) OU Code d'intégration Embed (<iframe>)", value=st.session_state.video_url, height=100)
            if st.button("Enregistrer le paramètre vidéo"):
                st.session_state.video_url = v_input
                st.success("Configuration vidéo enregistrée !")

        elif "⚡ 2." in admin_section:
            st.subheader("2. Banques de Questions-Flash Aléatoires")
            new_flash = []
            flash_curr = q_data.get("flash", [])
            nb_flash = st.number_input("Nombre de points d'arrêt flash", min_value=1, max_value=15, value=len(flash_curr))

            for j in range(int(nb_flash)):
                with st.expander(f"⚡ Point d'arrêt n°{j+1}", expanded=True):
                    f_item = flash_curr[j] if j < len(flash_curr) else {}
                    
                    c1, c2 = st.columns(2)
                    with c1: f_min = st.number_input("Minute", min_value=0, value=f_item.get("minutes", 0), key=f"fmin_{j}")
                    with c2: f_sec = st.number_input("Seconde", min_value=0, max_value=59, value=f_item.get("secondes", 0), key=f"fsec_{j}")
                    
                    mode_f = st.selectbox("Mode d'évaluation", ["Pas de bonne réponse (Orientation / Info)", "Avec réponse attendue (Évalué)"], index=0 if "Pas de bonne" in f_item.get("mode_reponse", "") else 1, key=f"fmode_{j}")

                    st.markdown("**Banque de questions pour ce timing (1 question par ligne avec réponse séparée par `|`) :**")
                    st.caption("Format : Intitulé de la question | Vrai (ou Faux)")
                    
                    banque_init = f_item.get("banque_questions", [])
                    banque_str_list = [f"{q.get('texte')} | {q.get('reponse', 'Vrai')}" for q in banque_init]
                    banque_raw = st.text_area("Questions de la banque :", value="\n".join(banque_str_list), key=f"fbanque_{j}")
                    
                    parsed_banque = []
                    for line in banque_raw.split("\n"):
                        if "|" in line:
                            parts = line.split("|")
                            parsed_banque.append({"texte": parts[0].strip(), "reponse": parts[1].strip()})
                        elif line.strip():
                            parsed_banque.append({"texte": line.strip(), "reponse": "Vrai"})

                    f_engins = st.checkbox("Déclenche le module engins si réponse VRAI", value=f_item.get("declenche_engins", False), key=f"feng_{j}")

                    new_flash.append({"minutes": f_min, "secondes": f_sec, "banque_questions": parsed_banque, "mode_reponse": mode_f, "declenche_engins": f_engins})

            if st.button("💾 Enregistrer la Banque de Questions-Flash"):
                q_data["flash"] = new_flash
                sauvegarder_questions(q_data)
                st.success("Banques de questions-flash enregistrées avec succès !")

        elif "📋 3." in admin_section:
            st.subheader("3. Questionnaire Général (Saisie Ligne par Ligne)")
            new_gen = []
            gen_questions = q_data.get("general", [])
            nb_gen = st.number_input("Nombre de questions générales", min_value=1, max_value=30, value=len(gen_questions))

            for i in range(int(nb_gen)):
                with st.expander(f"📋 Question n°{i+1}", expanded=True):
                    q_curr = gen_questions[i] if i < len(gen_questions) else {}
                    q_txt = st.text_input(f"Intitulé Question {i+1}", value=q_curr.get("texte", ""), key=f"qtxt_{i}")
                    opts_init_str = "\n".join(q_curr.get("options", [])) if isinstance(q_curr.get("options"), list) else q_curr.get("options", "")
                    opts_text = st.text_area("Options de réponse (1 option par ligne)", value=opts_init_str, key=f"optsarea_{i}")
                    opts_list = [line.strip() for line in opts_text.split("\n") if line.strip()]

                    rep_idx = 0
                    if opts_list:
                        default_rep = q_curr.get("reponse", 0)
                        rep_idx = default_rep if default_rep < len(opts_list) else 0
                        chosen_rep = st.radio("Cochez la bonne réponse attendue :", opts_list, index=rep_idx, key=f"chreprad_{i}")
                        rep_idx = opts_list.index(chosen_rep)

                    col_elim, col_pts = st.columns(2)
                    with col_elim: is_elim = st.checkbox("🚨 Question Éliminatoire", value=q_curr.get("eliminatoire", False), key=f"elim_{i}")
                    with col_pts: pts = st.number_input("Points (pas de 0.5)", min_value=0.5, max_value=5.0, step=0.5, value=float(q_curr.get("points", 1.0)), key=f"pts_{i}")

                    new_gen.append({"id": f"q_{i+1}", "texte": q_txt, "options": opts_list, "reponse": rep_idx, "points": pts, "eliminatoire": is_elim})

            if st.button("💾 Enregistrer le Questionnaire Général"):
                q_data["general"] = new_gen
                sauvegarder_questions(q_data)
                st.success("Questionnaire général enregistré !")

        elif "🚜 4." in admin_section:
            st.subheader("4. Module Spécifique Engins / Grues")
            new_eng = []
            eng_questions = q_data.get("engins", [])
            nb_eng = st.number_input("Nombre de questions engins", min_value=0, max_value=15, value=len(eng_questions))

            for k in range(int(nb_eng)):
                with st.expander(f"🚜 Question Engin n°{k+1}", expanded=True):
                    q_eng_curr = eng_questions[k] if k < len(eng_questions) else {}
                    q_eng_txt = st.text_input(f"Intitulé Question Engin {k+1}", value=q_eng_curr.get("texte", ""), key=f"qengtxt_{k}")
                    opts_eng_init_str = "\n".join(q_eng_curr.get("options", [])) if isinstance(q_eng_curr.get("options"), list) else q_eng_curr.get("options", "")
                    opts_eng_text = st.text_area("Options de réponse (1 par ligne)", value=opts_eng_init_str, key=f"optsengarea_{k}")
                    opts_eng_list = [line.strip() for line in opts_eng_text.split("\n") if line.strip()]

                    rep_eng_idx = 0
                    if opts_eng_list:
                        default_eng_rep = q_eng_curr.get("reponse", 0)
                        rep_eng_idx = default_eng_rep if default_eng_rep < len(opts_eng_list) else 0
                        chosen_eng_rep = st.radio("Cochez la bonne réponse engin attendue :", opts_eng_list, index=rep_eng_idx, key=f"chrepengrad_{k}")
                        rep_eng_idx = opts_eng_list.index(chosen_eng_rep)

                    pts_eng = st.number_input("Points engin", min_value=0.5, max_value=5.0, step=0.5, value=float(q_eng_curr.get("points", 1.0)), key=f"ptseng_{k}")
                    new_eng.append({"id": f"q_eng_{k+1}", "texte": q_eng_txt, "options": opts_eng_list, "reponse": rep_eng_idx, "points": pts_eng})

            if st.button("💾 Enregistrer le Questionnaire Engins"):
                q_data["engins"] = new_eng
                sauvegarder_questions(q_data)
                st.success("Questionnaire engins enregistré !")

        elif "📊 5." in admin_section:
            st.subheader("📊 Registre Historique Airtable")
            records_airtable = lire_airtable()
            if records_airtable:
                st.dataframe(pd.DataFrame(records_airtable), use_container_width=True)
            else:
                st.info("Aucune donnée disponible dans Airtable (vérifier la configuration des Secrets).")
    else:
        st.info("Saisissez le code secret administrateur pour accéder à la gestion.")
