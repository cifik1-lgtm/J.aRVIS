"""
RAG-Backed Expert Skills Consultant for JARVIS
Searches and executes guidelines from the 322 skills stored in the vector database.
"""

from core.llm_provider import call_llm
from core.integration_helper import load_integration_config, log_integration_event

def run(query: str, **kwargs):
    """
    Search RAG memory for expert skills matching the query and compile an elite analysis.
    """
    config = load_integration_config()
    
    if not config.get("rag_expert_skills", True):
        print("[expert_skills] ⏸️ Expert skills RAG disabled by config. Using static placeholder analysis.")
        return {
            "status": "success",
            "analysis": "Analyzed request for persistent memory integration using fallback approach.",
            "message": "Expert skills analysis completed (fallback mode - RAG disabled)"
        }

    print(f"[expert_skills] 🔍 Executing expert RAG analysis for query: '{query[:80]}...'")
    
    # 1. Retrieve RAG engine
    rag_context = ""
    retrieved_skills = []
    try:
        from memory.rag_engine import get_rag_engine
        rag = get_rag_engine()
        if rag and rag._ready:
            # 2. Search ChromaDB specifically for expert_skill category
            hits = rag.search(query, top_k=4, category_filter="expert_skill")
            
            if hits:
                lines = []
                for h in hits:
                    skill_name = h["key"].replace(".md", "").replace("_", " ").title()
                    retrieved_skills.append(h["key"])
                    lines.append(f"### SKILL RULESET: {skill_name}\n{h['value']}\n")
                rag_context = "\n".join(lines)
    except Exception as e:
        print(f"[expert_skills] ⚠️ RAG retrieval failed: {e}")

    # 3. Graceful Fallback if no skills are found or RAG is not ready
    if not rag_context:
        print("[expert_skills] ⚠️ No specific skill rulesets found in vector database. Falling back to general reasoning.")
        rag_context = "No specific rulesets found. Apply general software engineering best practices, Clean Architecture, and DRY principles."
        retrieved_skills = ["general_engineering_principles"]

    # 4. Construct Prompt
    system_instruction = (
        "You are the JARVIS Expert Skills Consultant, a highly sophisticated software architect and AI researcher.\n"
        "Your goal is to provide a premium, structured technical analysis of the user's query.\n"
        "You MUST align your response precisely with the retrieved skill guidelines below.\n\n"
        f"RETRIEVED EXPERT SKILL GUIDELINES:\n{rag_context}\n"
    )
    
    prompt = (
        f"USER CONSULTATION QUERY: {query}\n\n"
        "Provide a comprehensive, production-grade technical response. Structure your output clearly:\n"
        "1. Executive Summary\n"
        "2. Core Architectural & System Design\n"
        "3. Concrete Implementation Steps (with code/pseudocode where helpful)\n"
        "4. Applied Skill Rules (explicitly cite the retrieved skills used)\n\n"
        "Address the user as 'Sir Peter'. Keep your tone polished, witty, and exceptionally professional."
    )

    try:
        # 5. Call LLM
        analysis = call_llm(prompt, system_prompt=system_instruction, brain="pollinations", model="deepseek")
        
        # Log successful execution
        log_integration_event("expert_skills_exec", {
            "query": query,
            "skills_used": retrieved_skills,
            "status": "success"
        })
        
        return {
            "status": "success",
            "analysis": analysis,
            "skills_cited": retrieved_skills,
            "message": "Sir Peter, I have compiled the expert analysis based on my active rulesets."
        }
        
    except Exception as e:
        err_msg = str(e)
        log_integration_event("expert_skills_exec", {
            "query": query,
            "status": "failed",
            "error": err_msg
        })
        return {
            "status": "failed",
            "error": err_msg,
            "message": f"Sir Peter, I encountered an issue compiling the expert analysis: {err_msg[:120]}"
        }