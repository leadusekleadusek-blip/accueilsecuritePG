import os
import json
import time
import random
import string
import requests
from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import qrcode

# =========================================================================
# 1. CONFIGURATION & STYLES
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
        .flash-card {
            background-color: #FFF9E6; border: 3px solid #FFC107;
            padding: 25px; border-radius: 10px; margin: 20px 0; color: #222222;
        }
        .quiz-card {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 18px; border-radius: 8px; margin-bottom: 15px;
        }
        .waiting-box {
            background-color: #EBF8FF; border: 2px solid #3182CE;
            padding: 30px; border-radius: 10px; text-align: center; margin: 20px 0;
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
LOGO_PG_URL = "https://upload.wikimedia.org/wikipedia/commons/8/85/Procter_%26_Gamble_logo.svg"

# =========================================================================
# 2. PERSISTANCE CONFIGURATION & AIRTABLE
# =========================================================================

def charger_config():
    if not os.path.exists(QUESTIONS_FILE):
        cfg_def = {
            "video_url": "",
            "casques_rouges": {},
            "sessions_presentiel": {},
            "rattrapage_codes": {},
            "flash": [
                {
                    "minutes": 1, "secondes": 30,
                    "banque_questions": [
                        {"texte": "La limite de vitesse sur le site est de 20km/h", "reponse": "Vrai"},
                        {"texte": "La limite de vitesse sur le site est de 30km/h", "reponse": "Faux"}
                    ],
                    "mode_reponse": "Avec réponse attendue (Évalué)",
                    "declenche_engins": False
                }
            ],
            "general": [],
            "engins": []
        }
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg_def, f, ensure_ascii=False, indent=4)
        return cfg_def
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if "casques_rouges" not in data: data["casques_rouges"] = {}
        if "sessions_presentiel" not in data: data["sessions_presentiel"] = {}
        if "rattrapage_codes" not in data: data["rattrapage_codes"] = {}
        return data

def sauvegarder_config(data):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def enregistrer_airtable(d):
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID: return False
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "records": [{
            "fields": {
                "Nom": d.get("nom", ""),
                "Prenom": d.get("prenom", ""),
                "Entreprise": d.get("entreprise", ""),
                "EmailResponsable": d.get("email", ""),
                "Mode": d.get("mode", ""),
                "TempsPresenceMin": d.get("temps_presence", 0),
                "ScoreGeneral": float(d.get("score_general", 0)),
                "StatutGeneral": d.get("statut_general", ""),
                "MotifEchecInterne": d.get("motif_interne", "AUCUN"),
                "StatutEngins": d.get("statut_engins", "NON_CONCERNE"),
                "DatePassation": d.get("timestamp", "")
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

# INITIALISATION ÉTATS DE SESSION
if "step" not in st.session_state: st.session_state.step = 1
if "video_started" not in st.session_state: st.session_state.video_started = False
if "video_ended" not in st.session_state: st.session_state.video_ended = False
if "flash_repondues" not in st.session_state: st.session_state.flash_repondues = set()
if "questions_flash_tirees" not in st.session_state: st.session_state.questions_flash_tirees = {}
if "reponses_flash_engins" not in st.session_state: st.session_state.reponses_flash_engins = False
if "score_flash_correct" not in st.session_state: st.session_state.score_flash_correct = 0
if "total_flash_eval" not in st.session_state: st.session_state.total_flash_eval = 0
if "flash_msg_temp" not in st.session_state: st.session_state.flash_msg_temp = False
if "casque_rouge_logged" not in st.session_state: st.session_state.casque_rouge_logged = None

# =========================================================================
# 3. GENERATION PDF
# =========================================================================

def generer_pdf(d):
    filepath = os.path.join(FORMS_DIR, f"Pass_Securite_{d['nom']}_{d['prenom']}.pdf")
    doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#003B71'))
    subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=12, textColor=colors.HexColor('#4A5568'))
    label_style = ParagraphStyle('CellLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#003B71'))
    val_style = ParagraphStyle('CellVal', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=13, textColor=colors.HexColor('#2D3748'))

    logo_path = "temp_logo_pg.png"
    try:
        if not os.path.exists(logo_path):
            r_logo = requests.get(LOGO_PG_URL)
            if r_logo.status_code == 200:
                with open(logo_path, 'wb') as f: f.write(r_logo.content)
        img_logo = Image(logo_path, width=70, height=70)
    except Exception:
        img_logo = Paragraph("<font color='#003B71' size=24><b>P&amp;G</b></font>", styles['Normal'])

    header_table = Table([[img_logo, [Paragraph("ATTESTATION D'ACCUEIL SÉCURITÉ SITE", title_style), Spacer(1, 4), Paragraph("Procter &amp; Gamble Amiens — Direction HSE &amp; Sûreté", subtitle_style)]]], colWidths=[90, 450])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (0,0), 'CENTER')]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    sep_table = Table([['']], colWidths=[540], rowHeights=[3])
    sep_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#003B71'))]))
    story.append(sep_table)
    story.append(Spacer(1, 15))

    now = datetime.now()
    exp = datetime(now.year + 1, now.month, now.day)
    statut_engins_str = d.get('statut_engins', 'NON_CONCERNE')
    badge_engins = f"<font color='green'><b>AUTORISÉE</b></font>" if statut_engins_str == "AUTORISÉE" else "NON CONCERNÉ"

    table_data = [
        [Paragraph("NOM &amp; PRÉNOM", label_style), Paragraph(f"<b>{d['nom'].upper()}</b> {d['prenom'].capitalize()}", val_style)],
        [Paragraph("ENTREPRISE", label_style), Paragraph(d['entreprise'], val_style)],
        [Paragraph("DATE DE PASSATION", label_style), Paragraph(now.strftime('%d/%m/%Y à %H:%M'), val_style)],
        [Paragraph("DATE D'EXPIRATION", label_style), Paragraph(f"<b>{exp.strftime('%d/%m/%Y')}</b> <i>(Valable 1 an)</i>", val_style)],
        [Paragraph("DURÉE SESSION", label_style), Paragraph(f"{d.get('temps_presence', 40)} minutes (Conforme)", val_style)],
        [Paragraph("STATUT SÉCURITÉ", label_style), Paragraph("<font color='green'><b>🟢 ACCUEIL SÉCURITÉ VALIDÉ</b></font>", val_style)],
        [Paragraph("AUTORISATION ENGINS", label_style), Paragraph(badge_engins, val_style)]
    ]

    info_table = Table(table_data, colWidths=[160, 380])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F0F4F8')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    qr_payload = f"PG_AMIENS_PASS|{d['nom']}|{d['prenom']}|{d['entreprise']}|EXP:{exp.strftime('%Y%m%d')}"
    temp_qr_path = f"temp_qr_{d['nom']}.png"
    qr = qrcode.make(qr_payload)
    qr.save(temp_qr_path)

    qr_text = """
    <b>CONTRÔLE POSTE DE GARDE :</b><br/>
    <font size=8 color='#4A5568'>
    Ce Pass Sécurité atteste que l'intervenant a suivi l'intégralité de la sensibilisation aux risques du site P&amp;G Amiens et a validé le questionnaire de sécurité.<br/><br/>
    <b>Instructions :</b> Flasher le QR Code ci-contre pour vérifier la validité de l'attestation en base de données avant de délivrer le badge d'accès site.
    </font>
    """

    control_table = Table([[Image(temp_qr_path, width=95, height=95), Paragraph(qr_text, styles['Normal'])]], colWidths=[110, 430])
    control_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#003B71')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAFAFA')),
        ('PADDING', (0,0), (-1,-1), 10)
    ]))
    story.append(control_table)

    doc.build(story)
    return filepath

# =========================================================================
# 4. NAVIGATION LATERALE
# =========================================================================

st.sidebar.markdown("# **P&G Amiens**")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["🏢 Portail Intervenant", "⛑️ Espace Casque Rouge", "⚙️ Administrateur P&G"])
cfg = charger_config()

# =========================================================================
# SECTION 1 : PORTAIL INTERVENANT
# =========================================================================
if page == "🏢 Portail Intervenant":
    st.markdown("""<div class="main-header"><h1>🛡️ Accueil Sécurité Site — Procter & Gamble Amiens</h1></div>""", unsafe_allow_html=True)

    # ÉTAPE 1 : IDENTIFICATION & RACCORDEMENT
    if st.session_state.step == 1:
        st.markdown('<div class="section-card"><h2>👤 Étape 1 : Identification de l\'Intervenant</h2></div>', unsafe_allow_html=True)
        mode_passation = st.radio("Sélectionnez votre mode de formation :", ["DISTANCIEL (Autonome)", "SALLE / PRÉSENTIEL (Code de session)"])
        
        with st.form("form_id"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom").upper()
                prenom = st.text_input("Prénom").capitalize()
            with col2:
                entreprise = st.text_input("Entreprise Extérieure")
                email = st.text_input("E-mail du Responsable")

            code_session_input = ""
            if "PRÉSENTIEL" in mode_passation:
                code_session_input = st.text_input("Code de session fourni par le Casque Rouge (6 chiffres)", max_chars=6)

            if st.form_submit_button("Valider mes informations ➔"):
                if nom and prenom and entreprise:
                    if "PRÉSENTIEL" in mode_passation:
                        sessions_db = cfg.get("sessions_presentiel", {})
                        if code_session_input not in sessions_db:
                            st.error("Code de session invalide ou expiré.")
                            st.stop()
                        
                        # Inscription du candidat dans la session
                        s_data = sessions_db[code_session_input]
                        candidat_key = f"{nom}_{prenom}"
                        if candidat_key not in s_data.get("candidats_connectes", {}):
                            s_data.setdefault("candidats_connectes", {})[candidat_key] = {"nom": nom, "prenom": prenom}
                            cfg["sessions_presentiel"][code_session_input] = s_data
                            sauvegarder_config(cfg)
                    
                    st.session_state.user_data = {
                        "nom": nom, "prenom": prenom, "entreprise": entreprise, 
                        "email": email, "mode": mode_passation, "code_session": code_session_input
                    }
                    st.session_state.step = 2
                    st.rerun()
                else: st.error("Veuillez renseigner toutes vos informations nominatives.")

    # ÉTAPE 2 : ATTENTE SYNCHRO SALLE OU SÉANCE AUTONOME
    elif st.session_state.step == 2:
        ud = st.session_state.get("user_data", {})
        
        # CAS PRESENTIEL : ATTENTE DU DÉMARRAGE PAR L'ANIMATEUR
        if "PRÉSENTIEL" in ud.get("mode", ""):
            c_code = ud.get("code_session", "")
            s_data = cfg.get("sessions_presentiel", {}).get(c_code, {})
            nb_actuel = len(s_data.get("candidats_connectes", {}))
            nb_attendu = s_data.get("nb_attendus", 1)
            is_launched = s_data.get("launched", False)

            if not is_launched:
                st.markdown(f"""
                    <div class="waiting-box">
                        <h2>⏳ Session Salle en attente de démarrage...</h2>
                        <h3 style="color:#003B71; font-size:2rem;">👥 {nb_actuel} / {nb_attendu} candidat(s) connecté(s)</h3>
                        <p>Veuillez patienter. La vidéo va se lancer sur l'écran principal de la salle.</p>
                    </div>
                """, unsafe_allow_html=True)
                time.sleep(3)
                st.rerun()
            else:
                if not st.session_state.video_started:
                    st.session_state.video_started = True
                    st.session_state.start_time = datetime.now()

        # DÉROULEMENT CLASSIQUE (DISTANCIEL OU SALLE DÉMARRÉE)
        st.markdown('<div class="section-card"><h2>🎥 Étape 2 : Sensibilisation Vidéo & Questions-Flash</h2></div>', unsafe_allow_html=True)

        if not st.session_state.video_started:
            st.info("Cliquez ci-dessous pour démarrer le visionnage. Le chrono de la session s'activera.")
            if st.button("▶️ LANCER LA VIDÉO D'ACCUEIL SÉCURITÉ", type="primary"):
                st.session_state.video_started = True
                st.session_state.start_time = datetime.now()
                st.rerun()
        else:
            flash_list = cfg.get("flash", [])
            elapsed_sec = int((datetime.now() - st.session_state.start_time).total_seconds())

            flash_active_idx = None
            for idx, f in enumerate(flash_list):
                target_sec = (f.get("minutes", 0) * 60) + f.get("secondes", 0)
                if elapsed_sec >= target_sec and idx not in st.session_state.flash_repondues:
                    flash_active_idx = idx
                    break

            if st.session_state.flash_msg_temp:
                st.success("✅ **Réponse enregistrée.** Reprise de la vidéo...")
                time.sleep(1)
                st.session_state.flash_msg_temp = False
                st.rerun()

            elif flash_active_idx is not None:
                st.warning("⏸️ VIDÉO EN PAUSE — Question-Flash de contrôle (Délai : 30 secondes)")
                f_active = flash_list[flash_active_idx]

                if f"flash_timer_{flash_active_idx}" not in st.session_state:
                    st.session_state[f"flash_timer_{flash_active_idx}"] = datetime.now()

                time_spent = int((datetime.now() - st.session_state[f"flash_timer_{flash_active_idx}"]).total_seconds())
                time_left = max(0, 30 - time_spent)

                st.progress(time_left / 30)
                st.caption(f"⏳ Temps restant : **{time_left} seconde(s)**")

                if flash_active_idx not in st.session_state.questions_flash_tirees:
                    banque = f_active.get("banque_questions", [])
                    st.session_state.questions_flash_tirees[flash_active_idx] = random.choice(banque) if banque else {"texte": "Question non disponible", "reponse": "Vrai"}

                q_selected = st.session_state.questions_flash_tirees[flash_active_idx]

                if time_left > 0:
                    st.markdown(f'''
                        <div class="flash-card">
                            <h3>⚡ Question-Flash ({f_active.get("minutes",0)}m{f_active.get("secondes",0)}s)</h3>
                            <p style="font-size:1.15rem; font-weight:600;">{q_selected["texte"]}</p>
                        </div>
                    ''', unsafe_allow_html=True)

                    ans = st.radio("Votre réponse :", ["Vrai", "Faux"], key=f"rad_flash_{flash_active_idx}")

                    if st.button("Valider la réponse ➔"):
                        if ans == "Vrai" and f_active.get("declenche_engins"):
                            st.session_state.reponses_flash_engins = True

                        if f_active.get("mode_reponse") == "Avec réponse attendue (Évalué)":
                            st.session_state.total_flash_eval += 1
                            if ans == q_selected.get("reponse"):
                                st.session_state.score_flash_correct += 1

                        st.session_state.flash_repondues.add(flash_active_idx)
                        st.session_state.flash_msg_temp = True
                        st.rerun()
                else:
                    st.error("⌛ Temps écoulé (30s dépassées) pour cette question-flash !")
                    st.session_state.flash_repondues.add(flash_active_idx)
                    st.session_state.flash_msg_temp = True
                    time.sleep(1)
                    st.rerun()

            elif st.session_state.video_ended:
                st.markdown("---")
                if st.session_state.total_flash_eval > 0 and st.session_state.score_flash_correct == st.session_state.total_flash_eval:
                    st.success("🌟 **Super, vous avez été très attentif pendant la vidéo !**")
                else:
                    st.info("💡 **Veuillez rester bien attentif et concentré pour la suite.**")

                if st.button("Passer au questionnaire de validation des connaissances ➔", type="primary", use_container_width=True):
                    st.session_state.step = 3
                    st.rerun()

            else:
                # Si mode salle, la vidéo est sur l'écran principal
                if "PRÉSENTIEL" in ud.get("mode", ""):
                    st.info("📹 La vidéo est projetée sur l'écran principal de la salle. Gardez votre écran ouvert pour les questions-flash.")
                    if st.button("J'ai terminé le visionnage de la vidéo ➔"):
                        st.session_state.video_ended = True
                        st.rerun()
                else:
                    v_url = cfg.get("video_url", "")
                    if v_url:
                        if "iframe" in v_url.lower() or "embed" in v_url.lower():
                            st.components.v1.html(v_url, height=450)
                            if st.button("J'ai terminé le visionnage ➔", type="primary"):
                                st.session_state.video_ended = True
                                st.rerun()
                        else:
                            v_code = f"""
                            <div style="position: relative; width: 100%; max-width: 800px; margin: auto; user-select: none;">
                                <video id="pgVideo" width="100%" autoplay style="border-radius: 8px; pointer-events: none;">
                                    <source src="{v_url}" type="video/mp4">
                                </video>
                                <div style="position: absolute; top:0; left:0; width:100%; height:100%; z-index: 999; background: transparent;"></div>
                            </div>
                            <script>
                                const v = document.getElementById('pgVideo');
                                v.play();
                                setInterval(() => {{ if (v.playbackRate !== 1.0) v.playbackRate = 1.0; }}, 200);
                                document.addEventListener('contextmenu', e => e.preventDefault());
                            </script>
                            """
                            st.components.v1.html(v_code, height=460)

                            col_a, col_b = st.columns([3, 1])
                            with col_b:
                                if st.button("J'ai terminé le visionnage ➔"):
                                    st.session_state.video_ended = True
                                    st.rerun()
                    else:
                        st.warning("⚠️ Aucune URL vidéo configurée. Veuillez l'ajouter dans l'Espace Administrateur P&G.")

                time.sleep(3)
                st.rerun()

    # ÉTAPE 3 : QUESTIONNAIRE DE VALIDATION
    elif st.session_state.step == 3:
        st.markdown('<div class="section-card"><h2>📝 Étape 3 : Questionnaire de Validation</h2></div>', unsafe_allow_html=True)
        
        reponses_gen = {}
        st.markdown("### 📋 **Tronc Commun Général**")
        for idx, q in enumerate(cfg.get("general", [])):
            st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
            opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
            reponses_gen[idx] = st.radio(
                f"**Q{idx+1}. {q['texte']}** *(Barème : {q.get('points', 1.0)} pt)* {'*(🚨 Éliminatoire)*' if q.get('eliminatoire') else ''}", 
                opts, key=f"qgen_{idx}"
            )
            st.markdown('</div>', unsafe_allow_html=True)

        reponses_eng = {}
        if st.session_state.reponses_flash_engins and len(cfg.get("engins", [])) > 0:
            st.markdown("---")
            st.markdown("### 🚜 **Module Spécifique Engins / Grues**")
            for idx, q in enumerate(cfg.get("engins", [])):
                st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
                opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                reponses_eng[idx] = st.radio(f"**Q_Engin_{idx+1}. {q['texte']}**", opts, key=f"qeng_{idx}")
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
            st_canvas(stroke_width=2, stroke_color="#003B71", background_color="#FAFAFA", height=130, key="canvas_sig")

            if st.button("💾 Soumettre et Valider mon Accueil Sécurité"):
                score_gen = 0.0
                fautes_elim = 0

                start_t = st.session_state.get("start_time", datetime.now())
                temps_presence_min = int((datetime.now() - start_t).total_seconds() / 60)

                min_requis = 50 if st.session_state.reponses_flash_engins else 40
                max_autorise = 70 if st.session_state.reponses_flash_engins else 60

                reponses_gen = st.session_state.get("reponses_gen_val", {})
                for idx, q in enumerate(cfg.get("general", [])):
                    opts = q["options"] if isinstance(q["options"], list) else [o.strip() for o in q["options"].split(",")]
                    rep_ind = opts.index(reponses_gen[idx]) if idx in reponses_gen and reponses_gen[idx] in opts else -1
                    if rep_ind == int(q["reponse"]): score_gen += float(q.get("points", 1.0))
                    elif q.get("eliminatoire"): fautes_elim += 1

                ud = st.session_state.get("user_data", {"nom": "NOM", "prenom": "Prenom", "entreprise": "Entreprise"})
                ud["temps_presence"] = temps_presence_min
                ud["score_general"] = score_gen
                ud["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                tot_flash_cfg = len(cfg.get("flash", []))
                tot_flash_ok = len(st.session_state.flash_repondues)

                motif_interne = ""
                msg_candidat = ""

                if tot_flash_ok < tot_flash_cfg:
                    motif_interne = f"ECHEC_QUESTIONS_FLASH_MANQUANTES ({tot_flash_ok}/{tot_flash_cfg})"
                    msg_candidat = "Session invalide : Le visionnage complet de la vidéo de sensibilisation n'a pas été validé."
                elif temps_presence_min < min_requis:
                    motif_interne = "ECHEC_TEMPS_INSUFFISANT"
                    msg_candidat = "Votre session n'a pas été validée par le système. Veuillez contacter le service HSE."
                elif temps_presence_min > max_autorise:
                    motif_interne = "ECHEC_TEMPS_DEPASSE"
                    msg_candidat = "Votre session n'a pas été validée par le système. Veuillez contacter le service HSE."
                elif fautes_elim > 0:
                    motif_interne = f"ECHEC_QUESTION_ELIMINATOIRE ({fautes_elim} fautes)"
                    msg_candidat = "Échec : Au moins une erreur commise sur une règle éliminatoire de sécurité."
                elif score_gen < 1.0:
                    motif_interne = "ECHEC_SCORE_INSUFFISANT"
                    msg_candidat = "Score insuffisant au questionnaire de sécurité."

                ud["motif_interne"] = motif_interne if motif_interne else "AUCUN"

                if not motif_interne:
                    ud["statut_general"] = "VALIDE"
                    ud["statut_engins"] = "AUTORISÉE" if st.session_state.reponses_flash_engins else "NON_CONCERNE"
                    enregistrer_airtable(ud)
                    st.session_state.resultat_final = {"status": "SUCCESS", "data": ud, "pdf": generer_pdf(ud)}
                else:
                    ud["statut_general"] = "ECHEC"
                    ud["statut_engins"] = "NON_CONCERNE"
                    enregistrer_airtable(ud)
                    st.session_state.resultat_final = {"status": "FAILURE", "data": ud, "msg": msg_candidat}

                st.rerun()

        else:
            res = st.session_state.resultat_final
            if res.get("status") == "SUCCESS":
                st.balloons()
                st.success("🟢 ACCUEIL SÉCURITÉ VALIDÉ !")
                st.write(f"Bravo **{res['data']['prenom']} {res['data']['nom']}**, votre accueil sécurité est validé.")
                with open(res["pdf"], "rb") as f:
                    st.download_button("📄 Télécharger mon Attestation Sécurité PDF", f, file_name=os.path.basename(res["pdf"]))
            else:
                st.error("🔴 ACCUEIL SÉCURITÉ NON VALIDÉ")
                st.write(f"**Message :** {res.get('msg')}")
                
                st.markdown("---")
                st.subheader("🔑 Rattrapage par Code Unique")
                st.caption("Si vous disposez d'un code de rattrapage unique fourni par un Casque Rouge, saisissez-le ci-dessous.")
                
                code_ratt_input = st.text_input("Code de rattrapage (8 caractères)", max_chars=8).strip().upper()
                if st.button("Déverrouiller le rattrapage ➔"):
                    codes_db = cfg.get("rattrapage_codes", {})
                    if code_ratt_input in codes_db and not codes_db[code_ratt_input].get("utilise", False):
                        codes_db[code_ratt_input]["utilise"] = True
                        cfg["rattrapage_codes"] = codes_db
                        sauvegarder_config(cfg)

                        del st.session_state["resultat_final"]
                        st.session_state.step = 3
                        st.success("Code valide ! Redirection vers le questionnaire...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Code de rattrapage invalide ou déjà utilisé.")

            if st.button("Terminer la session"):
                del st.session_state["resultat_final"]
                st.session_state.step = 1
                st.session_state.video_started = False
                st.session_state.video_ended = False
                st.rerun()

# =========================================================================
# SECTION 2 : ESPACE CASQUE ROUGE (ANIMATION SALLE)
# =========================================================================
elif page == "⛑️ Espace Casque Rouge":
    st.markdown("""<div class="main-header"><h1>⛑️ Espace Animateurs Casque Rouge — P&G Amiens</h1></div>""", unsafe_allow_html=True)
    db_casques = cfg.get("casques_rouges", {})

    if not st.session_state.casque_rouge_logged:
        st.subheader("🔑 Connexion Casque Rouge")
        with st.form("form_login_cr"):
            email_cr = st.text_input("Adresse E-mail professionnelle").strip().lower()
            pwd_cr = st.text_input("Mot de passe", type="password")
            
            if st.form_submit_button("Se connecter ➔"):
                if email_cr in db_casques and db_casques[email_cr]["password"] == pwd_cr:
                    st.session_state.casque_rouge_logged = db_casques[email_cr]
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects ou compte inexistant.")
    else:
        cr_user = st.session_state.casque_rouge_logged
        st.sidebar.info(f"Connecté : **{cr_user['prenom']} {cr_user['nom']}**")
        if st.sidebar.button("Déconnexion"):
            st.session_state.casque_rouge_logged = None
            st.rerun()

        tab1, tab2, tab3 = st.tabs(["🎟️ Animation Session Salle (Kahoot)", "🔑 Codes de Rattrapage", "📊 Registre des Pass"])

        # ONGLET 1 : SESSIONS SALLE AVEC COMPTEUR DE CONNECTÉS
        with tab1:
            st.subheader("1. Créer une nouvelle session Salle")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                nb_attendus = st.number_input("Nombre de candidats attendus dans la salle", min_value=1, max_value=50, value=7)
            
            if st.button("🎟️ Activer la Session Salle ➔", type="primary"):
                s_code = ''.join(random.choices(string.digits, k=6))
                cfg["sessions_presentiel"][s_code] = {
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "cr_email": cr_user["email"],
                    "nb_attendus": nb_attendus,
                    "candidats_connectes": {},
                    "launched": False
                }
                sauvegarder_config(cfg)
                st.session_state.active_room_code = s_code
                st.rerun()

            # SUIVI EN DIRECT DE LA SESSION SALLE EN COURS
            if "active_room_code" in st.session_state and st.session_state.active_room_code in cfg.get("sessions_presentiel", {}):
                current_room_code = st.session_state.active_room_code
                room = cfg["sessions_presentiel"][current_room_code]

                st.markdown("---")
                st.subheader(f"📺 Écran de Contrôle Salle — Code : `{current_room_code}`")

                connectes = room.get("candidats_connectes", {})
                nb_conn = len(connectes)
                nb_att = room.get("nb_attendus", 7)

                st.markdown(f"""
                    <div class="waiting-box">
                        <h2 style="font-size: 2.5rem; color: #003B71;">👥 {nb_conn} / {nb_att} candidat(s) connecté(s)</h2>
                    </div>
                """, unsafe_allow_html=True)

                if connectes:
                    st.write("**Candidats dans la salle :** " + ", ".join([f"{v['prenom']} {v['nom']}" for v in connectes.values()]))

                # Lancement automatique dès que le quota est atteint
                if nb_conn >= nb_att and not room.get("launched"):
                    room["launched"] = True
                    cfg["sessions_presentiel"][current_room_code] = room
                    sauvegarder_config(cfg)
                    st.balloons()
                    st.success("🎉 Tous les candidats attendus sont connectés ! Démarrage automatique de la vidéo.")
                    st.rerun()

                if not room.get("launched"):
                    if st.button("▶️ Démarrer la vidéo pour la salle maintenant ➔"):
                        room["launched"] = True
                        cfg["sessions_presentiel"][current_room_code] = room
                        sauvegarder_config(cfg)
                        st.rerun()
                else:
                    st.success("🎥 **Vidéo de session en cours de projection sur cet écran principal.**")
                    v_url = cfg.get("video_url", "")
                    if v_url:
                        if "iframe" in v_url.lower() or "embed" in v_url.lower():
                            st.components.v1.html(v_url, height=500)
                        else:
                            st.video(v_url)

                time.sleep(3)
                st.rerun()

        with tab2:
            st.subheader("Générer un Code Unique de Rattrapage")
            nom_candidat = st.text_input("Nom & Prénom de l'intervenant éligible").upper()
            if st.button("Générer le Code Rattrapage ➔"):
                if nom_candidat:
                    r_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    cfg["rattrapage_codes"][r_code] = {
                        "candidat": nom_candidat,
                        "created_by": cr_user["email"],
                        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "utilise": False
                    }
                    sauvegarder_config(cfg)
                    st.success(f"Code généré pour {nom_candidat} : **{r_code}** (À usage unique)")
                else:
                    st.warning("Veuillez remplir le nom du candidat.")

        with tab3:
            st.subheader("Consultation du Registre des Accueils")
            rec = lire_airtable()
            if rec: st.dataframe(pd.DataFrame(rec), use_container_width=True)
            else: st.info("Aucune donnée enregistrée dans Airtable.")

# =========================================================================
# SECTION 3 : ADMINISTRATEUR P&G
# =========================================================================
elif page == "⚙️ Administrateur P&G":
    st.markdown("""<div class="main-header"><h1>⚙️ Panneau d'Administration Général P&G</h1></div>""", unsafe_allow_html=True)
    pwd_admin = st.sidebar.text_input("Code Secret Admin P&G", type="password")

    if pwd_admin == ADMIN_PASSWORD:
        st.sidebar.success("Accès Autorisé")
        admin_section = st.sidebar.radio("📌 Section Admin :", [
            "👥 1. Gestion Casques Rouges",
            "⚙️ 2. Vidéo Cloud", 
            "⚡ 3. Questions-Flash", 
            "📋 4. Questionnaire Général", 
            "🚜 5. Questionnaire Engins", 
            "📊 6. Registre Airtable"
        ])

        if "👥 1." in admin_section:
            st.subheader("1. Gestion des Utilisateurs Casque Rouge")
            with st.form("form_add_cr"):
                c_nom = st.text_input("Nom").upper()
                c_prenom = st.text_input("Prénom").capitalize()
                c_email = st.text_input("Adresse e-mail professionnelle").strip().lower()
                c_pwd = st.text_input("Mot de passe initial défini", type="password")

                if st.form_submit_button("Créer le compte Casque Rouge ➔"):
                    if c_nom and c_prenom and c_email and c_pwd:
                        cfg["casques_rouges"][c_email] = {
                            "nom": c_nom, "prenom": c_prenom, "email": c_email,
                            "password": c_pwd, "confirme": True,
                            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        sauvegarder_config(cfg)
                        st.success(f"Compte Casque Rouge créé pour **{c_prenom} {c_nom}** ({c_email}) !")
                    else: st.error("Veuillez remplir l'ensemble des champs.")

            st.markdown("---")
            st.subheader("Liste des Casques Rouges habilités :")
            st.json(cfg.get("casques_rouges", {}))

        elif "⚙️ 2." in admin_section:
            st.subheader("2. Vidéo Cloud Entreprise (.mp4 / Embed)")
            v_input = st.text_area("URL Directe MP4 ou Code Embed <iframe>", value=cfg.get("video_url", ""), height=100)
            if st.button("💾 Enregistrer l'URL Vidéo"):
                cfg["video_url"] = v_input
                sauvegarder_config(cfg)
                st.success("URL vidéo sauvegardée définitivement !")

        elif "⚡ 3." in admin_section:
            st.subheader("3. Banques de Questions-Flash")
            new_flash = []
            flash_curr = cfg.get("flash", [])
            nb_f = st.number_input("Nombre de points d'arrêt flash", min_value=1, max_value=15, value=len(flash_curr))

            for j in range(int(nb_f)):
                with st.expander(f"⚡ Point d'arrêt n°{j+1}", expanded=True):
                    f_item = flash_curr[j] if j < len(flash_curr) else {}
                    c1, c2 = st.columns(2)
                    with c1: f_min = st.number_input("Minute", min_value=0, value=f_item.get("minutes", 0), key=f"fmin_{j}")
                    with c2: f_sec = st.number_input("Seconde", min_value=0, max_value=59, value=f_item.get("secondes", 0), key=f"fsec_{j}")

                    mode_f = st.selectbox("Mode d'évaluation", ["Pas de bonne réponse (Orientation / Info)", "Avec réponse attendue (Évalué)"], index=0 if "Pas de bonne" in f_item.get("mode_reponse", "") else 1, key=f"fmode_{j}")

                    banque_init = f_item.get("banque_questions", [])
                    banque_str_list = [f"{q.get('texte')} | {q.get('reponse', 'Vrai')}" for q in banque_init]
                    banque_raw = st.text_area("Banque (Question | Vrai ou Faux)", value="\n".join(banque_str_list), key=f"fbanque_{j}")

                    parsed_b = []
                    for line in banque_raw.split("\n"):
                        if "|" in line:
                            p = line.split("|")
                            parsed_b.append({"texte": p[0].strip(), "reponse": p[1].strip()})
                        elif line.strip():
                            parsed_b.append({"texte": line.strip(), "reponse": "Vrai"})

                    f_eng = st.checkbox("Déclenche le module engins si réponse VRAI", value=f_item.get("declenche_engins", False), key=f"feng_{j}")
                    new_flash.append({"minutes": f_min, "secondes": f_sec, "banque_questions": parsed_b, "mode_reponse": mode_f, "declenche_engins": f_eng})

            if st.button("💾 Enregistrer les Questions-Flash"):
                cfg["flash"] = new_flash
                sauvegarder_config(cfg)
                st.success("Banques de questions-flash sauvegardées !")

        elif "📋 4." in admin_section:
            st.subheader("4. Questionnaire Général")
            new_gen = []
            gen_curr = cfg.get("general", [])
            nb_g = st.number_input("Nombre de questions générales", min_value=1, max_value=30, value=len(gen_curr))

            for i in range(int(nb_g)):
                with st.expander(f"📋 Question n°{i+1}", expanded=True):
                    q_item = gen_curr[i] if i < len(gen_curr) else {}
                    q_txt = st.text_input(f"Intitulé Question {i+1}", value=q_item.get("texte", ""), key=f"qtxt_{i}")
                    opts_init = "\n".join(q_item.get("options", [])) if isinstance(q_item.get("options"), list) else q_item.get("options", "")
                    opts_raw = st.text_area("Options (1 par ligne)", value=opts_init, key=f"opts_{i}")
                    opts_list = [l.strip() for l in opts_raw.split("\n") if l.strip()]

                    rep_idx = 0
                    if opts_list:
                        def_rep = q_item.get("reponse", 0)
                        rep_idx = def_rep if def_rep < len(opts_list) else 0
                        chosen = st.radio("Bonne réponse :", opts_list, index=rep_idx, key=f"ch_{i}")
                        rep_idx = opts_list.index(chosen)

                    c_elim, c_pts = st.columns(2)
                    with c_elim: is_elim = st.checkbox("🚨 Éliminatoire", value=q_item.get("eliminatoire", False), key=f"elim_{i}")
                    with c_pts: pts = st.number_input("Points", min_value=0.5, max_value=5.0, step=0.5, value=float(q_item.get("points", 1.0)), key=f"pts_{i}")

                    new_gen.append({"id": f"q_{i+1}", "texte": q_txt, "options": opts_list, "reponse": rep_idx, "points": pts, "eliminatoire": is_elim})

            if st.button("💾 Enregistrer le Questionnaire Général"):
                cfg["general"] = new_gen
                sauvegarder_config(cfg)
                st.success("Questionnaire général sauvegardé !")

        elif "🚜 5." in admin_section:
            st.subheader("5. Module Spécifique Engins / Grues")
            new_eng = []
            eng_curr = cfg.get("engins", [])
            nb_e = st.number_input("Nombre de questions engins", min_value=0, max_value=15, value=len(eng_curr))

            for k in range(int(nb_e)):
                with st.expander(f"🚜 Question Engin n°{k+1}", expanded=True):
                    q_e_item = eng_curr[k] if k < len(eng_curr) else {}
                    q_e_txt = st.text_input(f"Intitulé Question Engin {k+1}", value=q_e_item.get("texte", ""), key=f"qengtxt_{k}")
                    opts_e_init = "\n".join(q_e_item.get("options", [])) if isinstance(q_e_item.get("options"), list) else q_e_item.get("options", "")
                    opts_e_raw = st.text_area("Options engin (1 par ligne)", value=opts_e_init, key=f"optseng_{k}")
                    opts_e_list = [l.strip() for l in opts_e_raw.split("\n") if l.strip()]

                    rep_e_idx = 0
                    if opts_e_list:
                        def_e_rep = q_e_item.get("reponse", 0)
                        rep_e_idx = def_e_rep if def_e_rep < len(opts_e_list) else 0
                        chosen_e = st.radio("Bonne réponse engin :", opts_e_list, index=rep_e_idx, key=f"cheng_{k}")
                        rep_e_idx = opts_e_list.index(chosen_e)

                    pts_e = st.number_input("Points engin", min_value=0.5, max_value=5.0, step=0.5, value=float(q_e_item.get("points", 1.0)), key=f"ptseng_{k}")
                    new_eng.append({"id": f"q_eng_{k+1}", "texte": q_e_txt, "options": opts_e_list, "reponse": rep_e_idx, "points": pts_e})

            if st.button("💾 Enregistrer le Questionnaire Engins"):
                cfg["engins"] = new_eng
                sauvegarder_config(cfg)
                st.success("Questionnaire engins sauvegardé !")

        elif "📊 6." in admin_section:
            st.subheader("📊 Registre Historique Airtable")
            rec = lire_airtable()
            if rec: st.dataframe(pd.DataFrame(rec), use_container_width=True)
            else: st.info("Aucune donnée disponible.")
    else:
        st.info("Saisissez le code secret administrateur P&G pour accéder à la gestion.")
