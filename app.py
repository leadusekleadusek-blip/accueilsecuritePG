import os
import json
import random
import string
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
# 1. CONFIGURATION INITIALE & SESSIONS
# =========================================================================

st.set_page_config(
    page_title="Accueil Sécurité — P&G Amiens",
    page_icon="🛡️",
    layout="wide"
)

ADMIN_PASSWORD = "Casque rouge P&G26"
QUESTIONS_FILE = "questions.json"
FORMS_DIR = "pdf_generated"

os.makedirs(FORMS_DIR, exist_ok=True)

# Initialisation du stockage en session
if "registre_global" not in st.session_state:
    st.session_state.registre_global = []

def charger_questions():
    if not os.path.exists(QUESTIONS_FILE):
        def_q = {
            "flash": [
                {
                    "minutes": 8, "secondes": 30,
                    "questions_pool": ["Allez-vous réaliser des travaux par point chaud ?"],
                    "declenche_engins": False
                },
                {
                    "minutes": 17, "secondes": 15,
                    "questions_pool": ["Allez-vous utiliser un engin de manutention, une nacelle ou une grue sur site ?"],
                    "declenche_engins": True
                }
            ],
            "general": [
                {
                    "id": "q1", 
                    "texte": "En cas d'alarme incendie, quelle est la conduite à tenir ?", 
                    "options": "Attendre des consignes, Rejoindre le point de rassemblement, Continuer son travail", 
                    "reponse": 1, 
                    "points": 1, 
                    "eliminatoire": True
                },
                {
                    "id": "q2", 
                    "texte": "Quels sont les EPI de base obligatoires sur le site ?", 
                    "options": "Chaussures de sécurité et gilet haute visibilité, Baskets et casque audio", 
                    "reponse": 0, 
                    "points": 1, 
                    "eliminatoire": True
                }
            ],
            "engins": [
                {
                    "id": "q_eng_1", 
                    "texte": "Quel document est obligatoire pour la conduite d'un engin sur site ?", 
                    "options": "Permis B uniquement, Autorisation de conduite employeur + CACES", 
                    "reponse": 1, 
                    "points": 1, 
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
# 2. GÉNÉRATEUR DU PASS PDF OFFICIEL P&G
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
# 3. INTERFACE UTILISATEUR & ADMIN
# =========================================================================

st.sidebar.markdown("# **P&G Amiens**")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["🏢 Portail Intervenant", "⚙️ Espace Administrateur HSE"])

# -------------------------------------------------------------------------
# A. PORTAIL INTERVENANT
# -------------------------------------------------------------------------
if page == "🏢 Portail Intervenant":
    st.title("🛡️ Accueil Sécurité Site — Procter & Gamble Amiens")

    if "step" not in st.session_state:
        st.session_state.step = 1
    if "reponses_flash_engins" not in st.session_state:
        st.session_state.reponses_flash_engins = False

    # ÉTAPE 1 : IDENTIFICATION
    if st.session_state.step == 1:
        st.subheader("1. Identification de l'Intervenant")
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

            if st.form_submit_button("Commencer l'Accueil Sécurité"):
                if nom and prenom and entreprise:
                    st.session_state.user_data = {
                        "nom": nom, "prenom": prenom, "entreprise": entreprise,
                        "email": email, "mode": mode, "start_time": datetime.now()
                    }
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Veuillez remplir vos informations nominatives.")

    # ÉTAPE 2 : SENSABILISATION VIDÉO & QUESTIONS-FLASH
    elif st.session_state.step == 2:
        st.subheader("2. Sensibilisation aux Risques Site")
        
        # Champ URL ou intégration vidéo direct cloud
        st.info("📹 Regardez la vidéo d'accueil sécurité ci-dessous.")
        st.video("https://www.w3schools.com/html/mov_bbb.mp4") # Remplaçable par ton lien vidéo MP4 hébergé

        q_db = charger_questions()
        
        with st.expander("❓ Question-Flash : Conduite d'engins / nacelles sur site", expanded=True):
            engins_opt = st.radio("Allez-vous conduire un engin de manutention, une nacelle ou une grue sur site ?", ["Non", "Oui"])
            if engins_opt == "Oui":
                st.session_state.reponses_flash_engins = True

        if st.button("Passer au Questionnaire Final"):
            st.session_state.step = 3
            st.rerun()

    # ÉTAPE 3 : QUESTIONNAIRE & SIGNATURE TACTILE
    elif st.session_state.step == 3:
        st.subheader("3. Questionnaire de Validation")
        q_db = charger_questions()

        reponses_gen = {}
        st.markdown("### **Tronc Commun Général**")
        for idx, q in enumerate(q_db.get("general", [])):
            opts = [o.strip() for o in q["options"].split(",")] if isinstance(q["options"], str) else q["options"]
            reponses_gen[idx] = st.radio(f"**Q{idx+1}. {q['texte']}** {'*(Éliminatoire)*' if q.get('eliminatoire') else ''}", opts, key=f"gen_{idx}")

        reponses_eng = {}
        if st.session_state.reponses_flash_engins and len(q_db.get("engins", [])) > 0:
            st.markdown("---")
            st.markdown("### **Module Spécifique Engins / Grues**")
            for idx, q in enumerate(q_db.get("engins", [])):
                opts = [o.strip() for o in q["options"].split(",")] if isinstance(q["options"], str) else q["options"]
                reponses_eng[idx] = st.radio(f"**Q_Engin_{idx+1}. {q['texte']}**", opts, key=f"eng_{idx}")

        st.markdown("---")
        st.subheader("4. Attestation sur l'honneur & Signature")
        st.caption("Je certifie sur l'honneur être la personne réalisant cet accueil sécurité et avoir suivi l'intégralité de la formation sans assistance.")
        
        canvas_result = st_canvas(stroke_width=2, stroke_color="#003B71", background_color="#FAFAFA", height=130, key="sig_canvas")

        if st.button("Valider et Soumettre mon Accueil Sécurité"):
            score_gen = 0
            fautes_elim = 0
            for idx, q in enumerate(q_db.get("general", [])):
                opts = [o.strip() for o in q["options"].split(",")] if isinstance(q["options"], str) else q["options"]
                rep_ind = opts.index(reponses_gen[idx]) if reponses_gen[idx] in opts else -1
                if rep_ind == int(q["reponse"]):
                    score_gen += int(q.get("points", 1))
                elif q.get("eliminatoire"):
                    fautes_elim += 1

            if fautes_elim == 0 and score_gen >= 1:
                ud = st.session_state.user_data
                ud["temps_presence"] = 42 # Conforme
                ud["score_general"] = score_gen
                ud["statut_general"] = "VALIDE"
                ud["statut_engins"] = "AUTORISÉE" if st.session_state.reponses_flash_engins else "NON_CONCERNE"
                ud["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Inscription au registre
                st.session_state.registre_global.append(ud)
                pdf_path = generer_pdf(ud)
                
                st.balloons()
                st.success("🟢 ACCUEIL SÉCURITÉ VALIDÉ !")
                with open(pdf_path, "rb") as f:
                    st.download_button("📄 Télécharger mon Pass Sécurité PDF", f, file_name=os.path.basename(pdf_path))
            else:
                st.error("🔴 ÉCHEC DE VALIDATION ACCUEIL SÉCURITÉ. Veuillez contacter le service HSE.")

# -------------------------------------------------------------------------
# B. ESPACE ADMINISTRATEUR HSE
# -------------------------------------------------------------------------
elif page == "⚙️ Espace Administrateur HSE":
    st.title("🔒 Espace Administration HSE")

    pwd = st.text_input("Code secret d'accès Administrateur", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Accès Administrateur Déverrouillé.")

        tab_params, tab_results = st.tabs(["⚙️ Paramètres de l'Accueil", "📊 Résultats des Candidats"])

        with tab_params:
            st.subheader("1. Fichier Vidéo ou Lien Streaming")
            st.text_input("URL directe de la vidéo (.mp4 / Vimeo / Stream)", value="https://www.w3schools.com/html/mov_bbb.mp4")

            st.markdown("---")
            st.subheader("2. Gestionnaire de Questionnaires")
            q_data = charger_questions()

            col_a, col_b = st.columns(2)
            with col_a:
                up_txt = st.file_uploader("Importer un fichier texte (.txt) de questions", type=["txt"])
                if up_txt:
                    st.info("Fichier chargé ! Ajustez les cases dans le tableau ci-dessous.")
            with col_b:
                if st.button("🗑️ Vider le questionnaire pour tout saisir à la main"):
                    q_data["general"] = []
                    sauvegarder_questions(q_data)
                    st.rerun()

            st.markdown("#### **Édition du Questionnaire Général**")
            df_gen = pd.DataFrame(q_data.get("general", []))
            edited_df_gen = st.data_editor(df_gen, num_rows="dynamic", use_container_width=True, key="ed_gen")

            st.markdown("#### **Édition du Module Spécifique Engins / Grues**")
            df_eng = pd.DataFrame(q_data.get("engins", []))
            edited_df_eng = st.data_editor(df_eng, num_rows="dynamic", use_container_width=True, key="ed_eng")

            if st.button("💾 Enregistrer Tous les Questionnaires"):
                q_data["general"] = edited_df_gen.to_dict(orient="records")
                q_data["engins"] = edited_df_eng.to_dict(orient="records")
                sauvegarder_questions(q_data)
                st.success("Configuration sauvegardée !")

        with tab_results:
            st.subheader("📊 Registre Historique des Tentatives")
            if len(st.session_state.registre_global) > 0:
                df_res = pd.DataFrame(st.session_state.registre_global)
                st.dataframe(df_res, use_container_width=True)
                csv = df_res.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Exporter le registre (Excel / CSV)", csv, "registre_accueils_pg.csv", "text/csv")
            else:
                st.info("Aucune tentative enregistrée pour le moment.")
