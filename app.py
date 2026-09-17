import os
import json
import base64
from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet
import qrcode

# =========================================================================
# 1. CONFIGURATION INITIALE & STYLES ADAPTATIFS (LIGHT & DARK MODE)
# =========================================================================

st.set_page_config(
    page_title="Accueil Sécurité — P&G Amiens",
    page_icon="🛡️",
    layout="wide"
)

# CSS adaptatif utilisant les variables de thème dynamiques de Streamlit
st.markdown("""
    <style>
        /* Police globale */
        html, body, [class*="css"] {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }

        /* En-tête principal P&G - compatible Mode Sombre et Clair */
        .main-header {
            background: linear-gradient(135deg, #003B71 0%, #005691 100%);
            padding: 20px;
            border-radius: 10px;
            color: #FFFFFF !important;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
        }
        .main-header h1 {
            color: #FFFFFF !important;
            margin: 0;
            font-size: 1.8rem;
            font-weight: 700;
        }

        /* Cartes de sections adaptatives */
        .section-card {
            background-color: var(--secondary-background-color);
            border-left: 6px solid #003B71;
            padding: 18px 22px;
            border-radius: 6px;
            margin-top: 20px;
            margin-bottom: 20px;
            color: var(--text-color);
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        /* Cartes Questions-Flash */
        .flash-card {
            background-color: var(--secondary-background-color);
            border-left: 6px solid #FFC107;
            padding: 16px 20px;
            border-radius: 6px;
            margin-bottom: 15px;
            color: var(--text-color);
        }

        /* Conteneurs de questions */
        .quiz-card {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 18px;
            border-radius: 8px;
            margin-bottom: 15px;
            color: var(--text-color);
        }

        /* Ajustement des boutons principaux */
        div.stButton > button {
            border-radius: 6px;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

ADMIN_PASSWORD = "Casque rouge P&G26"
QUESTIONS_FILE = "questions.json"
FORMS_DIR = "pdf_generated"

os.makedirs(FORMS_DIR, exist_ok=True)

if "registre_global" not in st.session_state:
    st.session_state.registre_global = []

if "video_url" not in st.session_state:
    st.session_state.video_url = ""

def charger_questions():
    if not os.path.exists(QUESTIONS_FILE):
        def_q = {
            "flash": [
                {
                    "minutes": 8, "secondes": 30,
                    "texte": "Allez-vous réaliser des travaux par point chaud ?",
                    "reponse": "Faux",
                    "points": 0.5,
                    "declenche_engins": False
                },
                {
                    "minutes": 17, "secondes": 15,
                    "texte": "Allez-vous utiliser un engin de manutention, une nacelle ou une grue sur site ?",
                    "reponse": "Vrai",
                    "points": 0.5,
                    "declenche_engins": True
                }
            ],
            "general": [
                {
                    "id": "q1", 
                    "texte": "En cas d'alarme incendie, quelle est la conduite à tenir ?", 
                    "options": ["Attendre des consignes", "Rejoindre le point de rassemblement", "Continuer son travail"], 
                    "reponse": 1, 
                    "points": 1.0, 
                    "eliminatoire": True
                }
            ],
            "engins": [
                {
                    "id": "q_eng_1", 
                    "texte": "Quel document est obligatoire pour la conduite d'un engin sur site ?", 
                    "options": ["Permis B uniquement", "Autorisation de conduite employeur + CACES"], 
                    "reponse": 1, 
                    "points": 1.0, 
                    "eliminatoire": True
                }
            ]
        }
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(def_q, f, ensure_ascii=False, indent=4)
        return def_q
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def sauvegarder_questions(data):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================================
# 2. GENERATION DU PASS PDF OFFICIEL P&G
# =========================================================================

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
# 3. INTERFACE UTILISATEUR & ESPACE ADMIN
# =========================================================================

st.sidebar.markdown("# **P&G Amiens**")
st.sidebar.markdown("---")
page = st.sidebar.radio("Accès Portail", ["🏢 Portail Intervenant", "⚙️ Espace Administrateur HSE"])

# -------------------------------------------------------------------------
# A. PORTAIL INTERVENANT (PARCOURS SÉQUENTIEL SANS SAUT DE PAGE POSSIBLE)
# -------------------------------------------------------------------------
if page == "🏢 Portail Intervenant":
    st.markdown("""
        <div class="main-header">
            <h1>🛡️ Accueil Sécurité Site — Procter & Gamble Amiens</h1>
        </div>
    """, unsafe_allow_html=True)

    if "step" not in st.session_state:
        st.session_state.step = 1
    if "reponses_flash_engins" not in st.session_state:
        st.session_state.reponses_flash_engins = False

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
            code_salle = ""
            if "SALLE" in mode:
                code_salle = st.text_input("Code de session à 6 chiffres (affiché en salle)")

            if st.form_submit_button("Valider mes informations et passer à la vidéo ➔"):
                if nom and prenom and entreprise:
                    st.session_state.user_data = {
                        "nom": nom, "prenom": prenom, "entreprise": entreprise,
                        "email": email, "mode": mode, "start_time": datetime.now()
                    }
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Veuillez remplir vos informations nominatives.")

    # ÉTAPE 2 : VISIONNAGE VIDÉO & QUESTIONS-FLASH
    elif st.session_state.step == 2:
        st.markdown('<div class="section-card"><h2>🎥 Étape 2 : Sensibilisation Vidéo & Questions-Flash</h2></div>', unsafe_allow_html=True)
        
        v_url = st.session_state.video_url
        if v_url:
            st.video(v_url)
        else:
            st.info("📹 Regardez la vidéo d'accueil sécurité ci-dessous.")
            st.warning("⚠️ L'URL de la vidéo officielle entreprise est à configurer dans l'Espace Admin.")

        st.markdown("---")
        st.markdown('<div class="flash-card"><h3>⚡ Questions-Flash d\'Auto-évaluation</h3></div>', unsafe_allow_html=True)
        
        q_db = charger_questions()
        flash_list = q_db.get("flash", [])
        
        reponses_flash_user = {}
        if len(flash_list) > 0:
            for idx, f in enumerate(flash_list):
                with st.container():
                    st.markdown(f"**Question-Flash ({f.get('minutes',0)}m{f.get('secondes',0)}s) : {f.get('texte','')}**")
                    ans = st.radio(
                        "Votre réponse :", 
                        ["Vrai", "Faux"], 
                        key=f"flash_{idx}"
                    )
                    reponses_flash_user[idx] = ans
                    if ans == "Vrai" and f.get("declenche_engins"):
                        st.session_state.reponses_flash_engins = True

        if st.button("Passer au Questionnaire Final ➔"):
            st.session_state.step = 3
            st.rerun()

    # ÉTAPE 3 : QUESTIONNAIRES DE VALIDATION
    elif st.session_state.step == 3:
        st.markdown('<div class="section-card"><h2>📝 Étape 3 : Questionnaire de Validation</h2></div>', unsafe_allow_html=True)
        q_db = charger_questions()

        reponses_gen = {}
        st.markdown("### 📋 **Tronc Commun Général**")
        for idx, q in enumerate(q_db.get("general", [])):
            st.markdown(f'<div class="quiz-card">', unsafe_allow_html=True)
            opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
            reponses_gen[idx] = st.radio(
                f"**Q{idx+1}. {q['texte']}** *(Barème : {q.get('points', 1.0)} pt)* {'*(🚨 Éliminatoire)*' if q.get('eliminatoire') else ''}", 
                opts, 
                key=f"gen_{idx}"
            )
            st.markdown('</div>', unsafe_allow_html=True)

        reponses_eng = {}
        if st.session_state.reponses_flash_engins and len(q_db.get("engins", [])) > 0:
            st.markdown("---")
            st.markdown("### 🚜 **Module Spécifique Engins / Grues**")
            for idx, q in enumerate(q_db.get("engins", [])):
                st.markdown(f'<div class="quiz-card">', unsafe_allow_html=True)
                opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                reponses_eng[idx] = st.radio(
                    f"**Q_Engin_{idx+1}. {q['texte']}** *(Barème : {q.get('points', 1.0)} pt)*", 
                    opts, 
                    key=f"eng_{idx}"
                )
                st.markdown('</div>', unsafe_allow_html=True)

        if st.button("Passer à l'Émargement & Signature ➔"):
            st.session_state.step = 4
            st.rerun()

    # ÉTAPE 4 : SIGNATURE & RÉSULTATS
    elif st.session_state.step == 4:
        st.markdown('<div class="section-card"><h2>✍️ Étape 4 : Attestation sur l\'honneur & Validation</h2></div>', unsafe_allow_html=True)
        
        if "resultat_final" not in st.session_state:
            st.caption("Je certifie sur l'honneur être la personne réalisant cet accueil sécurité et avoir suivi la formation sans assistance.")
            canvas_result = st_canvas(stroke_width=2, stroke_color="#003B71", background_color="#FAFAFA", height=130, key="sig_canvas")

            if st.button("💾 Soumettre et Valider mon Accueil Sécurité"):
                q_db = charger_questions()
                score_gen = 0.0
                fautes_elim = 0
                
                for idx, q in enumerate(q_db.get("general", [])):
                    opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                    rep_ind = opts.index(reponses_gen[idx]) if idx in reponses_gen and reponses_gen[idx] in opts else -1
                    if rep_ind == int(q["reponse"]):
                        score_gen += float(q.get("points", 1.0))
                    elif q.get("eliminatoire"):
                        fautes_elim += 1

                ud = st.session_state.get("user_data", {"nom": "NOM", "prenom": "Prenom", "entreprise": "Entreprise"})
                ud["temps_presence"] = 42
                ud["score_general"] = score_gen
                ud["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if fautes_elim == 0 and score_gen >= 1.0:
                    ud["statut_general"] = "VALIDE"
                    ud["statut_engins"] = "AUTORISÉE" if st.session_state.reponses_flash_engins else "NON_CONCERNE"
                    st.session_state.registre_global.append(ud)
                    st.session_state.resultat_final = {"status": "SUCCESS", "data": ud, "pdf": generer_pdf(ud)}
                else:
                    ud["statut_general"] = "ECHEC"
                    ud["statut_engins"] = "NON_CONCERNE"
                    st.session_state.registre_global.append(ud)
                    st.session_state.resultat_final = {"status": "FAILURE", "data": ud}

                st.rerun()
        else:
            res = st.session_state.resultat_final
            if res.get("status") == "SUCCESS":
                st.balloons()
                st.success("🟢 ACCUEIL SÉCURITÉ VALIDÉ !")
                st.write(f"Félicitations **{res['data']['prenom']} {res['data']['nom']}**, votre score final est de **{res['data']['score_general']} pt(s)**.")
                
                with open(res["pdf"], "rb") as f:
                    st.download_button("📄 Télécharger mon Attestation Sécurité PDF", f, file_name=os.path.basename(res["pdf"]))
            else:
                st.error("🔴 ÉCHEC DE VALIDATION DE L'ACCUEIL SÉCURITÉ")
                st.write(f"Désolé **{res['data']['prenom']} {res['data']['nom']}**, votre résultat ne permet pas de valider l'accès au site.")
                st.write("Veuillez contacter le service HSE P&G Amiens.")

            if st.button("Terminer et recommencer"):
                del st.session_state["resultat_final"]
                st.session_state.step = 1
                st.rerun()

# -------------------------------------------------------------------------
# B. ESPACE ADMINISTRATEUR HSE
# -------------------------------------------------------------------------
elif page == "⚙️ Espace Administrateur HSE":
    st.markdown("""
        <div class="main-header">
            <h1>🔒 Panneau d'Administration HSE — P&G Amiens</h1>
        </div>
    """, unsafe_allow_html=True)

    pwd = st.sidebar.text_input("Code secret Administrateur", type="password")
    if pwd == ADMIN_PASSWORD:
        st.sidebar.success("Accès Administrateur Autorisé")
        
        admin_section = st.sidebar.radio(
            "📌 Section Admin :",
            ["⚙️ 1. Vidéo Cloud", "⚡ 2. Questions-Flash", "📋 3. Questionnaire Général", "🚜 4. Questionnaire Engins", "📊 5. Registre des Résultats"]
        )

        q_data = charger_questions()

        if "⚙️ 1." in admin_section:
            st.subheader("1. Vidéo Cloud Entreprise (Stream / SharePoint / Drive)")
            v_input = st.text_input("URL directe de la vidéo d'accueil sécurité (.mp4 / Stream)", value=st.session_state.video_url)
            if st.button("Enregistrer l'URL de la vidéo"):
                st.session_state.video_url = v_input
                st.success("URL vidéo enregistrée !")

        elif "⚡ 2." in admin_section:
            st.subheader("2. Questions-Flash pendant la vidéo (Vrai / Faux)")
            new_flash = []
            flash_curr = q_data.get("flash", [])
            nb_flash = st.number_input("Nombre de questions-flash", min_value=1, max_value=15, value=len(flash_curr))

            for j in range(int(nb_flash)):
                with st.expander(f"⚡ Question-Flash n°{j+1}", expanded=True):
                    f_item = flash_curr[j] if j < len(flash_curr) else {}
                    f_txt = st.text_input(f"Intitulé de la question-flash {j+1}", value=f_item.get("texte", ""), key=f"ftxt_{j}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1: f_min = st.number_input("Minute d'arrêt", min_value=0, value=f_item.get("minutes", 0), key=f"fmin_{j}")
                    with c2: f_sec = st.number_input("Seconde d'arrêt", min_value=0, max_value=59, value=f_item.get("secondes", 0), key=f"fsec_{j}")
                    with c3: f_rep = st.selectbox("Réponse attendue", ["Vrai", "Faux"], index=0 if f_item.get("reponse") == "Vrai" else 1, key=f"frep_{j}")

                    col_pts_f, col_eng_f = st.columns(2)
                    with col_pts_f: f_pts = st.number_input("Points (pas 0.5)", min_value=0.5, max_value=2.0, step=0.5, value=float(f_item.get("points", 0.5)), key=f"fpts_{j}")
                    with col_eng_f: f_engins = st.checkbox("Déclenche le module engins si VRAI", value=f_item.get("declenche_engins", False), key=f"feng_{j}")

                    new_flash.append({"minutes": f_min, "secondes": f_sec, "texte": f_txt, "reponse": f_rep, "points": f_pts, "declenche_engins": f_engins})

            if st.button("💾 Enregistrer les Questions-Flash"):
                q_data["flash"] = new_flash
                sauvegarder_questions(q_data)
                st.success("Questions-Flash enregistrées !")

        elif "📋 3." in admin_section:
            st.subheader("3. Questionnaire Général (Tronc Commun)")
            new_gen = []
            gen_questions = q_data.get("general", [])
            nb_gen = st.number_input("Nombre de questions générales", min_value=1, max_value=30, value=len(gen_questions))

            for i in range(int(nb_gen)):
                with st.expander(f"📋 Question n°{i+1}", expanded=True):
                    q_curr = gen_questions[i] if i < len(gen_questions) else {}
                    q_txt = st.text_input(f"Intitulé {i+1}", value=q_curr.get("texte", ""), key=f"qtxt_{i}")
                    opts_init = ", ".join(q_curr.get("options", [])) if isinstance(q_curr.get("options"), list) else q_curr.get("options", "")
                    opts_raw = st.text_input(f"Options (séparées par des virgules)", value=opts_init, key=f"optsraw_{i}")
                    opts_list = [o.strip() for o in opts_raw.split(",") if o.strip()]
                    
                    rep_idx = 0
                    if opts_list:
                        default_rep = q_curr.get("reponse", 0)
                        rep_idx = default_rep if default_rep < len(opts_list) else 0
                        chosen_rep = st.selectbox("Bonne réponse attendue", opts_list, index=rep_idx, key=f"chrep_{i}")
                        rep_idx = opts_list.index(chosen_rep)

                    col_elim, col_pts = st.columns(2)
                    with col_elim: is_elim = st.checkbox("🚨 Question Éliminatoire", value=q_curr.get("eliminatoire", False), key=f"elim_{i}")
                    with col_pts: pts = st.number_input("Points (pas 0.5)", min_value=0.5, max_value=5.0, step=0.5, value=float(q_curr.get("points", 1.0)), key=f"pts_{i}")

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
                    q_eng_txt = st.text_input(f"Intitulé question engin {k+1}", value=q_eng_curr.get("texte", ""), key=f"qengtxt_{k}")
                    opts_eng_init = ", ".join(q_eng_curr.get("options", [])) if isinstance(q_eng_curr.get("options"), list) else q_eng_curr.get("options", "")
                    opts_eng_raw = st.text_input(f"Options (séparées par des virgules)", value=opts_eng_init, key=f"optsengraw_{k}")
                    opts_eng_list = [o.strip() for o in opts_eng_raw.split(",") if o.strip()]
                    
                    rep_eng_idx = 0
                    if opts_eng_list:
                        default_eng_rep = q_eng_curr.get("reponse", 0)
                        rep_eng_idx = default_eng_rep if default_eng_rep < len(opts_eng_list) else 0
                        chosen_eng_rep = st.selectbox("Bonne réponse engin attendue", opts_eng_list, index=rep_eng_idx, key=f"chrepeng_{k}")
                        rep_eng_idx = opts_eng_list.index(chosen_eng_rep)

                    pts_eng = st.number_input("Points engin", min_value=0.5, max_value=5.0, step=0.5, value=float(q_eng_curr.get("points", 1.0)), key=f"ptseng_{k}")

                    new_eng.append({"id": f"q_eng_{k+1}", "texte": q_eng_txt, "options": opts_eng_list, "reponse": rep_eng_idx, "points": pts_eng})

            if st.button("💾 Enregistrer le Questionnaire Engins"):
                q_data["engins"] = new_eng
                sauvegarder_questions(q_data)
                st.success("Questionnaire engins enregistré !")

        elif "📊 5." in admin_section:
            st.subheader("📊 Registre Historique des Tentatives de Validation")
            if len(st.session_state.registre_global) > 0:
                df_res = pd.DataFrame(st.session_state.registre_global)
                st.dataframe(df_res, use_container_width=True)
                csv = df_res.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Exporter le registre sous Excel (CSV)", csv, "registre_accueils_pg.csv", "text/csv")
            else:
                st.info("Aucun résultat enregistré pour le moment.")
    else:
        st.info("Veuillez saisir le code d'accès administrateur dans le menu de gauche pour déverrouiller la gestion.")
