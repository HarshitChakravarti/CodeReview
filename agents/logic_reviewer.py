import json
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import Finding

# Identical retry logic to the security scanner. Parallel agents might hit 
# rate limits simultaneously, so robust backoff is critical here.
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_gemini_with_retry(llm: ChatGoogleGenerativeAI, prompt: str) -> str:
    response = llm.invoke(prompt)
    return response.content

def logic_reviewer_node(state: dict) -> dict:
    print("Running Logic Reviewer...")
    findings: List[Finding] = []
    
    # Temperature 0 keeps the reviewer focused on tangible logic errors 
    # rather than overly creative or nitpicky style suggestions.
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # The prompt is structurally identical to the security scanner, but focuses
    # entirely on code quality, maintainability, and bugs.
    system_instruction = (
        "You are an expert senior software engineer reviewing code logic. Analyze the diff. "
        "Find functions that are too long, missing error handling, logic bugs, dead code, "
        "or poor variable naming. "
        "Respond ONLY with a valid JSON array of objects. Do not use markdown blocks like ```json. "
        "Each object must have the exact following keys: "
        "'file' (string), 'line' (integer, guess the line number if unsure), "
        "'severity' (one of: 'critical', 'warning', 'info'), "
        "'description' (string explaining the logic issue)."
    )

    for file_chunk in state.get("file_diffs", []):
        filename = file_chunk.get("filename", "unknown")
        diff_text = file_chunk.get("diff", "")
        
        # Trim to 3000 chars to respect context limits and maintain speed.
        trimmed_diff = diff_text[:3000]
        
        prompt = f"{system_instruction}\n\nFile: {filename}\nDiff:\n{trimmed_diff}"
        
        try:
            response_text = call_gemini_with_retry(llm, prompt)
            
            # Clean markdown block wrappers if the LLM includes them despite instructions
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            if cleaned_text:
                issues = json.loads(cleaned_text)
                for issue in issues:
                    # Category is explicitly set to "logic" to differentiate 
                    # from the "security" findings when they are merged in the state.
                    finding = Finding(
                        file=issue.get("file", filename),
                        line=issue.get("line", 0),
                        severity=issue.get("severity", "warning"),
                        category="logic",
                        description=issue.get("description", "Unknown logic issue")
                    )
                    findings.append(finding)
                    
        except json.JSONDecodeError as e:
            print(f"[Logic Reviewer] Failed to parse JSON for {filename}: {e}")
        except Exception as e:
            print(f"[Logic Reviewer] Error processing {filename}: {e}")

    return {"findings": findings}
