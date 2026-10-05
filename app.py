import json
import os
from dotenv import load_dotenv

import streamlit as st
from docx import Document
from pypdf import PdfReader
from google import genai


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-3.5-flash-lite"

REPORT_SECTIONS = [
    ("strengths", "Strengths"),
    ("gaps", "Gaps"),
    ("missing_or_weak_skills", "Missing or Weak Skills"),
    ("improvement_suggestions", "Improvement Suggestion"),
    ("overall_summary", "Overall Summary"),
]


def extract_resume_text(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        pages = []

        for page in reader.pages:
            pages.append(page.extract_text() or "")

        return "\n".join(pages).strip()

    if file_name.endswith(".docx"):
        document = Document(uploaded_file)
        paragraphs = []

        for p in document.paragraphs:
            paragraphs.append(p.text)

        return "\n".join(paragraphs).strip()

    return "NO INPUT WAS GIVEN AS CV."


def analyze_resume(resume_text, job_description):

    client = genai.Client(api_key=API_KEY)

    instructions = """You compare resumes against job descriptions.

Reply with JSON only, using exactly these keys.
Every value must be a list of short strings.

{
  "candidate_skills": [],
  "candidate_experience": [],
  "candidate_qualifications": [],
  "required_skills": [],
  "preferred_skills": [],
  "matching_skills": [],
  "missing_skills": [],
  "gaps": []
}

Rules:
- Use only information that actually appears in the resume or job description.
- Never invent skills, employers, job titles, dates, certifications or achievements.
- "missing_skills" means the job description asks for it and the resume does not mention it.
- Leave a list empty when the text gives you nothing to put in it.
"""

    user_message = f"""Compare this resume against this job description and reply with JSON.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=instructions + "\n\n" + user_message,
        config={
            "response_mime_type": "application/json",
        },
    )

    return json.loads(response.text)


def generate_final_report(structured_analysis):

    client = genai.Client(api_key=API_KEY)

    instructions = """You write short, honest resume feedback for a candidate.

Reply with JSON only, using exactly these keys.
Every value is a string.

{
  "strengths": "",
  "gaps": "",
  "missing_or_weak_skills": "",
  "improvement_suggestions": "",
  "overall_summary": ""
}

Rules:
- Write the first four values as Markdown bullet lists.
- Write "overall_summary" as one short paragraph.
- Never leave a value empty.
- Base everything on the JSON you are given.
- Do not invent anything new.
"""

    user_message = f"""
Turn this structured data into resume feedback and reply with JSON.

{json.dumps(structured_analysis, indent=2)}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=instructions + "\n\n" + user_message,
        config={
            "response_mime_type": "application/json",
        },
    )

    report = json.loads(response.text)

    for key, _ in REPORT_SECTIONS:
        value = report.get(key)

        if isinstance(value, list):
            value = "\n".join("- " + str(point) for point in value)

        report[key] = value or "Nothing was reported for this section."

    return report


def create_downloadable_report(final_report):

    lines = ["# Resume Analysis"]

    for key, heading in REPORT_SECTIONS:
        lines.append(f"## {heading}")
        lines.append(final_report[key])

    return "\n\n".join(lines)


def main():

    st.set_page_config(page_title="AI Resume Analyzer")

    st.title("AI Resume Analyzer")

    st.write(
        "Upload your resume and paste a JOB Description to identify strengths, "
        "gaps and improvement opportunities."
    )

    uploaded_file = st.file_uploader(
        "Upload your resume",
        type=["pdf", "docx"]
    )

    job_description = st.text_area(
        "Paste the Job Description",
        height=250
    )

    if st.button("Analyze Resume"):

        if uploaded_file is None:
            st.warning("Please upload your resume")
            st.stop()

        if not job_description.strip():
            st.warning("Please paste the JD.")
            st.stop()

        resume_text = extract_resume_text(uploaded_file)

        if not resume_text:
            st.warning("No text could be read from your resume file.")
            st.stop()

        if not API_KEY:
            st.error("No Gemini API key was found in .env file.")
            st.stop()

        with st.spinner("Analyze your resume..."):

            try:
                structured_analysis = analyze_resume(
                    resume_text,
                    job_description
                )

                final_report = generate_final_report(
                    structured_analysis
                )

            except Exception as error:
                st.error(f"The analysis failed: {error}")
                st.stop()

        st.session_state["final_report"] = final_report

        final_report = st.session_state["final_report"]

        st.divider()
        st.subheader("Analysis Results")

        for key, heading in REPORT_SECTIONS:
            st.markdown("### " + heading)
            st.markdown(final_report[key])

        st.download_button(
            "Download Report",
            data=create_downloadable_report(final_report),
            file_name="resume_analysis.md",
        )


if __name__ == "__main__":
    main()