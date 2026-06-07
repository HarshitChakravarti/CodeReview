from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import ReviewState

def review_writer_node(state: ReviewState) -> dict:
    """
    Synthesizes the findings from the security and logic agents, as well as the 
    Docker test results, into a cohesive GitHub-flavored markdown PR review.
    """
    print("Writing Draft Review...")
    findings = state.get("findings", [])
    test_results = state.get("test_results", "No test results provided.")
    
    # Sort findings by severity so Critical issues always appear at the top.
    # We use a custom order mapping for the sort key.
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    sorted_findings = sorted(
        findings, 
        key=lambda f: severity_order.get(f.severity.lower(), 3)
    )
    
    # Format the findings into a text block to feed into the LLM
    findings_text = ""
    for f in sorted_findings:
        findings_text += f"[{f.severity.upper()}] [{f.category.upper()}] in {f.file} (Line {f.line}): {f.description}\n"
        
    if not findings_text:
        findings_text = "No logic or security issues found."

    # Using temperature 0.2 for a slightly more natural, conversational prose 
    # compared to the strict analytical outputs of the scanning agents.
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    
    prompt = f"""
    You are an expert senior software engineer writing a code review for a GitHub Pull Request.
    
    Using the following static analysis findings and dynamic test results, draft a comprehensive 
    GitHub-flavored markdown review. 
    
    Required Sections:
    1. Summary
    2. Critical Issues [CRITICAL]
    3. Warnings [WARN]
    4. Suggestions [INFO]
    5. Test Results
    
    Static Analysis Findings:
    {findings_text}
    
    Dynamic Test Results (Pytest):
    {test_results}
    
    Write the review naturally. Do not just blindly copy-paste the logs; synthesize them 
    into actionable feedback for the developer. If tests failed, explain why based on the output.
    """
    
    from tenacity import retry, stop_after_attempt, wait_exponential
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
    def call_with_retry():
        return llm.invoke(prompt)

    try:
        response = call_with_retry()
        content = response.content
    except Exception as e:
        print(f"[Review Writer] Failed to generate review due to API error: {e}")
        content = f"Error generating review: {str(e)}"
    
    return {"draft_review": content}
