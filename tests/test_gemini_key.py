from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
response = llm.invoke(
    "Please review this Python function briefly: def add(a, b): return a + b"
)

print(response)
