import json
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import Finding

# Tenacity is used here to make our system resilient to transient network errors 
# or rate limits from the Google Gemini API. It will try up to 3 times, backing off exponentially.
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_gemini_with_retry(llm: ChatGoogleGenerativeAI, prompt: str) -> str:
    response = llm.invoke(prompt)
    return response.content

def security_scanner_node(state: dict) -> dict:
    print("Running Security Scanner...")
    findings: List[Finding] = []
    
    # Initialize the LLM with a temperature of 0 for deterministic, analytical outputs.
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    system_instruction = (
        "You are an expert security reviewer. Analyze the following code diff. "
        "Find hardcoded secrets, SQL injection, dangerous functions (eval, exec, pickle.loads), "
        "missing input validation, or insecure dependencies. "
        "Respond ONLY with a valid JSON array of objects. Do not use markdown blocks like ```json. "
        "Each object must have the exact following keys: "
        "'file' (string), 'line' (integer, guess the line number if unsure), "
        "'severity' (one of: 'critical', 'warning', 'info'), "
        "'description' (string explaining the vulnerability)."
    )

    for file_chunk in state.get("file_diffs", []):
        filename = file_chunk.get("filename", "unknown")
        diff_text = file_chunk.get("diff", "")
        
        # Trim the diff to avoid exceeding the context window and speed up processing.
        # 3000 characters is a safe limit for a single file's chunk in this setup.
        trimmed_diff = diff_text[:3000]
        
        prompt = f"{system_instruction}\n\nFile: {filename}\nDiff:\n{trimmed_diff}"
        
        try:
            # Call the LLM with our retry wrapper
            response_text = call_gemini_with_retry(llm, prompt)
            
            # Clean up potential markdown formatting from the response
            # Sometimes LLMs ignore the "no markdown" instruction
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            # Parse the JSON response
            if cleaned_text:
                issues = json.loads(cleaned_text)
                for issue in issues:
                    # Convert the JSON dictionary into our Finding dataclass
                    finding = Finding(
                        file=issue.get("file", filename),
                        line=issue.get("line", 0),
                        severity=issue.get("severity", "warning"),
                        category="security",
                        description=issue.get("description", "Unknown security issue")
                    )
                    findings.append(finding)
                    
        except json.JSONDecodeError as e:
            # We wrap parsing in a try/except because LLM output can be unpredictable.
            # Crashing the entire graph because of one bad output is poor UX.
            print(f"[Security Scanner] Failed to parse JSON for {filename}: {e}")
        except Exception as e:
            print(f"[Security Scanner] Error processing {filename}: {e}")

    # Return the findings. Because of the Annotated operator.add in our state,
    # these will be merged with findings from other agents.
    return {"findings": findings}
