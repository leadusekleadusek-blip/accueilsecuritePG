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
# 1. CONFIGURATION INITIALE & SESSIONS CLOUD
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
                    "reponse": "Non",
                    "points": 0.5,
                    "declenche_engins": False
                },
                {
                    "minutes": 17, "secondes": 15,
                    "texte": "Allez-vous utiliser un engin de manutention, une nacelle ou une grue sur site ?",
                    "reponse": "Oui",
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

    # ÉTAPE 2 : VISIONNAGE VIDÉO & QUESTIONS-FLASH (VRAI / FAUX)
    elif st.session_state.step == 2:
        st.subheader("2. Sensibilisation aux Risques Site")
        
        v_url = st.session_state.video_url
        if v_url:
            st.video(v_url)
        else:
            st.info("📹 Regardez la vidéo d'accueil sécurité ci-dessous.")
            st.warning("⚠️ L'URL de la vidéo officielle entreprise est à configurer dans l'Espace Admin.")

        q_db = charger_questions()
        st.markdown("---")
        st.subheader("❓ Questions-Flash (Auto-évaluation)")
        
        flash_list = q_db.get("flash", [])
        if len(flash_list) > 0:
            for idx, f in enumerate(flash_list):
                ans = st.radio(
                    f"**Question-Flash ({f.get('minutes',0)}m{f.get('secondes',0)}s) : {f.get('texte','')}**", 
                    ["Vrai", "Faux"], 
                    key=f"flash_{idx}"
                )
                if ans == "Vrai" and f.get("declenche_engins"):
                    st.session_state.reponses_flash_engins = True

        if st.button("Accéder au Questionnaire Final"):
            st.session_state.step = 3
            st.rerun()

    # ÉTAPE 3 : QUESTIONNAIRES DE VALIDATION
    elif st.session_state.step == 3:
        st.subheader("3. Questionnaire de Validation")
        q_db = charger_questions()

        reponses_gen = {}
        st.markdown("### **Tronc Commun Général**")
        for idx, q in enumerate(q_db.get("general", [])):
            opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
            reponses_gen[idx] = st.radio(
                f"**Q{idx+1}. {q['texte']}** *(Barème : {q.get('points', 1.0)} pt)* {'*(Éliminatoire)*' if q.get('eliminatoire') else ''}", 
                opts, 
                key=f"gen_{idx}"
            )

        st.markdown("---")
        st.subheader("4. Attestation sur l'honneur & Signature")
        st.caption("Je certifie sur l'honneur être la personne réalisant cet accueil sécurité et avoir suivi la formation sans assistance.")
        
        canvas_result = st_canvas(stroke_width=2, stroke_color="#003B71", background_color="#FAFAFA", height=130, key="sig_canvas")

        if st.button("Valider et Soumettre mon Accueil Sécurité"):
            score_gen = 0.0
            fautes_elim = 0
            for idx, q in enumerate(q_db.get("general", [])):
                opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                rep_ind = opts.index(reponses_gen[idx]) if reponses_gen[idx] in opts else -1
                if rep_ind == int(q["reponse"]):
                    score_gen += float(q.get("points", 1.0))
                elif q.get("eliminatoire"):
                    fautes_elim += 1

            ud = st.session_state.user_data
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

            st.session_state.step = 4
            st.rerun()

    # ÉTAPE 4 : ÉCRAN FINAL (RÉSULTATS ET ATTENTION PDF)
    elif st.session_state.step == 4:
        res = st.session_state.get("resultat_final", {})
        if res.get("status") == "SUCCESS":
            st.balloons()
            st.success("🟢 ACCUEIL SÉCURITÉ VALIDÉ !")
            st.write(f"Bravo **{res['data']['prenom']} {res['data']['nom']}**, votre score final est de **{res['data']['score_general']} pt(s)**.")
            
            with open(res["pdf"], "rb") as f:
                st.download_button("📄 Télécharger mon Attestation Sécurité PDF", f, file_name=os.path.basename(res["pdf"]))
        else:
            st.error("🔴 ÉCHEC DE VALIDATION DE L'ACCUEIL SÉCURITÉ")
            st.write(f"Désolé **{res['data']['prenom']} {res['data']['nom']}**, votre résultat ne permet pas de valider l'accès au site.")
            st.write("Veuillez contacter le service HSE P&G Amiens.")

        if st.button("Terminer et revenir à l'accueil"):
            st.session_state.step = 1
            st.rerun()

# -------------------------------------------------------------------------
# B. ESPACE ADMINISTRATEUR HSE (STYLE MICROSOFT FORMS)
# -------------------------------------------------------------------------
elif page == "⚙️ Espace Administrateur HSE":
    st.title("🔒 Espace Administration HSE")

    pwd = st.text_input("Code secret d'accès Administrateur", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Accès Administrateur Déverrouillé.")

        tab_params, tab_results = st.tabs(["⚙️ Paramètres & Questionnaires", "📊 Enregistrement des Résultats"])

        with tab_params:
            st.subheader("1. Vidéo Cloud Entreprise (Stream / SharePoint / Drive)")
            v_input = st.text_input("URL directe de la vidéo d'accueil sécurité (.mp4 / Stream)", value=st.session_state.video_url)
            if st.button("Enregistrer l'URL de la vidéo"):
                st.session_state.video_url = v_input
                st.success("URL vidéo enregistrée !")

            st.markdown("---")
            q_data = charger_questions()

            # 2. QUESTIONS-FLASH (VRAI / FAUX)
            st.subheader("2. Questions-Flash pendant la vidéo (Vrai / Faux)")
            new_flash = []
            flash_curr = q_data.get("flash", [])
            nb_flash = st.number_input("Nombre de questions-flash", min_value=1, max_value=15, value=len(flash_curr))

            for j in range(int(nb_flash)):
                with st.expander(f"⚡ Question-Flash n°{j+1}", expanded=True):
                    f_item = flash_curr[j] if j < len(flash_curr) else {}
                    
                    f_txt = st.text_input(f"Intitulé de la question-flash {j+1}", value=f_item.get("texte", ""), key=f"ftxt_{j}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        f_min = st.number_input("Minute d'arrêt", min_value=0, value=f_item.get("minutes", 0), key=f"fmin_{j}")
                    with c2:
                        f_sec = st.number_input("Seconde d'arrêt", min_value=0, max_value=59, value=f_item.get("secondes", 0), key=f"fsec_{j}")
                    with c3:
                        f_rep = st.selectbox("Réponse attendue", ["Vrai", "Faux"], index=0 if f_item.get("reponse") == "Vrai" else 1, key=f"frep_{j}")

                    col_pts_f, col_eng_f = st.columns(2)
                    with col_pts_f:
                        f_pts = st.number_input("Points attribués", min_value=0.5, max_value=2.0, step=0.5, value=float(f_item.get("points", 0.5)), key=f"fpts_{j}")
                    with col_eng_f:
                        f_engins = st.checkbox("Déclenche le module engins si VRAI", value=f_item.get("declenche_engins", False), key=f"feng_{j}")

                    new_flash.append({
                        "minutes": f_min,
                        "secondes": f_sec,
                        "texte": f_txt,
                        "reponse": f_rep,
                        "points": f_pts,
                        "declenche_engins": f_engins
                    })

            st.markdown("---")

            # 3. QUESTIONNAIRE GENERAL (POINTS PAR 0.5)
            st.subheader("3. Questionnaire Général (Tronc Commun)")
            new_gen = []
            gen_questions = q_data.get("general", [])
            nb_gen = st.number_input("Nombre de questions générales", min_value=1, max_value=30, value=len(gen_questions))

            for i in range(int(nb_gen)):
                with st.expander(f"📋 Question n°{i+1}", expanded=True):
                    q_curr = gen_questions[i] if i < len(gen_questions) else {}
                    
                    q_txt = st.text_input(f"Intitulé de la question {i+1}", value=q_curr.get("texte", ""), key=f"qtxt_{i}")
                    
                    opts_init = ", ".join(q_curr.get("options", [])) if isinstance(q_curr.get("options"), list) else q_curr.get("options", "")
                    opts_raw = st.text_input(f"Options de réponse (séparées par une virgule)", value=opts_init, key=f"optsraw_{i}")
                    opts_list = [o.strip() for o in opts_raw.split(",") if o.strip()]
                    
                    rep_idx = 0
                    if opts_list:
                        default_rep = q_curr.get("reponse", 0)
                        rep_idx = default_rep if default_rep < len(opts_list) else 0
                        chosen_rep = st.selectbox("Bonne réponse attendue", opts_list, index=rep_idx, key=f"chrep_{i}")
                        rep_idx = opts_list.index(chosen_rep)

                    col_elim, col_pts = st.columns(2)
                    with col_elim:
                        is_elim = st.checkbox("🚨 Question Éliminatoire", value=q_curr.get("eliminatoire", False), key=f"elim_{i}")
                    with col_pts:
                        pts = st.number_input("Points attribués (pas de 0.5)", min_value=0.5, max_value=5.0, step=0.5, value=float(q_curr.get("points", 1.0)), key=f"pts_{i}")

                    new_gen.append({
                        "id": f"q_{i+1}",
                        "texte": q_txt,
                        "options": opts_list,
                        "reponse": rep_idx,
                        "points": pts,
                        "eliminatoire": is_elim
                    })

            if st.button("💾 Enregistrer la Configuration des Questionnaires"):
                q_data["general"] = new_gen
                q_data["flash"] = new_flash
                sauvegarder_questions(q_data)
                st.success("Questionnaires enregistrés avec succès !")

        # ONGLET REGISTRE DES RÉSULTATS
        with tab_results:
            st.subheader("📊 Registre Historique des Tentatives de Validation")
            if len(st.session_state.registre_global) > 0:
                df_res = pd.DataFrame(st.session_state.registre_global)
                st.dataframe(df_res, use_container_width=True)
                
                csv = df_res.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Exporter le registre sous Excel (CSV)", csv, "registre_accueils_pg.csv", "text/csv")
            else:
                st.info("Aucun résultat enregistré pour le moment.")
