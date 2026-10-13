from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[1] / "output" / "pdf" / "Aditya_Kurup_Guidewire_Resume.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#236A8A")
GRAY = colors.HexColor("#4B5563")
LIGHT = colors.HexColor("#D6E3EA")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="Name", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=19,
    leading=21, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2,
))
styles.add(ParagraphStyle(
    name="Contact", parent=styles["Normal"], fontName="Helvetica", fontSize=7.8,
    leading=10, textColor=GRAY, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="Section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.2,
    leading=11, textColor=NAVY, spaceBefore=4, spaceAfter=2,
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["Normal"], fontName="Helvetica", fontSize=7.65,
    leading=9.15, textColor=colors.HexColor("#202833"), spaceAfter=1.4,
))
styles.add(ParagraphStyle(
    name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2,
    leading=8.6, textColor=colors.HexColor("#202833"),
))
styles.add(ParagraphStyle(
    name="Role", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.2,
    leading=9.6, textColor=NAVY,
))

def p(text, style="Body"):
    return Paragraph(text, styles[style])

def section(title):
    return [p(title.upper(), "Section"), Table([['']], colWidths=[7.45 * inch], rowHeights=[0.6], style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), LIGHT)]))]

def bullets(items):
    return [p(f"&#8226; {item}") for item in items]

doc = SimpleDocTemplate(
    str(OUT), pagesize=letter, leftMargin=0.48 * inch, rightMargin=0.48 * inch,
    topMargin=0.34 * inch, bottomMargin=0.32 * inch, title="Aditya Kurup Resume",
    author="Aditya Kurup",
)
story = []
story += [
    p("Aditya Kurup", "Name"),
    p("Bengaluru, India  |  <link href='mailto:adityakurup05@gmail.com' color='#236A8A'>adityakurup05@gmail.com</link>  |  +91 8779642950  |  <link href='https://linkedin.com/in/aditya-kurup' color='#236A8A'>LinkedIn</link>  |  <link href='https://github.com/aditya-kurup' color='#236A8A'>GitHub</link>", "Contact"),
    Spacer(1, 3),
]
story += section("About")
story += [p("Computer Science (AI) undergraduate building practical automation with Python, LLMs, AWS, and Slack applications. Experienced in schema validated model workflows, evaluation, secure approval gates, and reproducible testing. I enjoy learning unfamiliar systems quickly, communicating technical tradeoffs clearly, and owning reliable deliverables from design through verification.")]

story += section("Education")
story += [p("<b>Manipal Institute of Technology</b>, Bengaluru, India <font color='#4B5563'>| B.Tech in Computer Science (AI), Minor in Quantum Computing | 2023-2027</font>"), p("<b>CGPA:</b> 8.47/10  |  <b>Coursework:</b> Machine Learning, Operating Systems, Computer Networks, Data Structures and Algorithms, DBMS, Probability, Statistics, Linear Algebra", "Small")]

story += section("Experience")
story += [p("AI Intern, <b>Zino Technologies</b> - Bengaluru, Karnataka <font color='#4B5563'>| Jun 2025 - Jul 2025</font>", "Role")]
story += bullets([
    "Built Python LLM workflows that converted free-form product descriptions into schema validated JSON for a low-code B2B SaaS platform, rejecting malformed generations before downstream code generation.",
    "Wrote an evaluation harness comparing prompt variants and foundation models on output validity and schema conformance; used data driven results to select the shipped workflow.",
])
story += [p("Research Intern, <b>Qomputing.ai</b> - Bengaluru, Karnataka <font color='#4B5563'>| Mar 2026 - Apr 2026</font>", "Role")]
story += bullets([
    "Developed Python simulation backends for statevector execution, implementing low level compute paths that step circuits through gate sequences.",
    "Profiled batched numerical workloads, located bottlenecks in per gate update loops, and restructured hot paths to improve throughput.",
])

story += section("Projects")
story += [p("<b>OpsPilot Lite - Approval Gated AWS Provisioning</b> | <link href='https://github.com/aditya-kurup/opspilot-lite' color='#236A8A'>GitHub</link> <font color='#4B5563'>| Python, Slack Bolt, DeepSeek, boto3, AWS CDK</font>", "Role")]
story += bullets([
    "Built a working Slack workflow that converts natural language requests into strict JSON plans, validates them with Pydantic, and requires approval from a separate allowlisted user.",
    "Implemented an allowlisted boto3 S3 executor with dry run mode, encryption, public access blocking, TTL and ownership tags, audit logging, duplicate prevention, and expired empty bucket cleanup.",
    "Added CDK deployment infrastructure for Lambda, API Gateway, SQS, DynamoDB, EventBridge, and Secrets Manager; verified the local Slack to LLM to approval flow end to end.",
])
story += [p("<b>Policy Gated Growth Agent</b> | <link href='https://github.com/aditya-kurup' color='#236A8A'>GitHub</link> <font color='#4B5563'>| Python, Gemini API, Razorpay API</font>", "Role")]
story += bullets(["Designed deterministic policy and atomic reservation layers so model output could propose offers but never make money affecting decisions; validated 629 oracle cases and stress tested 5,000 concurrent attempts with zero overdraws."])
story += [p("<b>LLM Self Correction Reliability Study</b> | <link href='https://github.com/aditya-kurup' color='#236A8A'>GitHub</link> <font color='#4B5563'>| Python, Pandas, NumPy, Scikit learn, SQL</font>", "Role")]
story += bullets(["Built a reproducible evaluation pipeline covering 5,760 test events across four models and trained a question grouped logistic gate that improved pooled accuracy by 2.59 percentage points over baseline."])

story += section("Technical Skills")
story += [p("<b>Languages:</b> Python, Go, C, Java, SQL, JavaScript  |  <b>AI/ML:</b> LLM APIs, prompt evaluation, schema validation, RAG, Scikit learn, TensorFlow, PyTorch, NumPy, Pandas  |  <b>Cloud & Automation:</b> AWS (S3, Lambda, DynamoDB, EventBridge), AWS CDK, Slack Apps, REST APIs, Git, Linux  |  <b>Exposure:</b> Jenkins, ServiceNow workflows, infrastructure as code, cloud security, Agile/Scrum", "Small")]

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.25 * inch, letter[0] - doc.rightMargin, 0.25 * inch)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(doc.leftMargin, 0.13 * inch, "Aditya Kurup | AI Engineering | Cloud Automation")
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.13 * inch, "1")
    canvas.restoreState()

doc.build(story, onFirstPage=footer)
print(OUT)
