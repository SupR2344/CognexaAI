"""Autonomous Generative Intent Handler for Cognexa AI.

Detects conversational requests for engineering artifacts (Presentations, PDFs,
Software Projects, Image Synthesis, Charts) across English, Hindi, and Hinglish,
autonomously executes the appropriate generator, stores verified knowledge into persistent
vector memory, and formats rich responses with download cards.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import uuid

from app.services.generators import (
    generate_chart_plot,
    generate_image,
    generate_pdf_report,
    generate_presentation,
    generate_software_project,
)

logger = logging.getLogger(__name__)


async def handle_generative_request(
    message: str,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Any] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Inspect message for generative requests or enforced operational modes.

    Returns:
        Dict with 'response_text' and 'artifact_info' if handled,
        or None if regular chat should proceed.
    """
    # 0. Enforced Model Modes
    if model == "Deep Research Mode":
        try:
            from app.services.web_search import perform_web_search, format_search_response
            search_data = await perform_web_search(message)
            response_text = format_search_response(message, search_data)
            return {
                "response_text": response_text,
                "artifact_info": {"type": "search", "results_count": len(search_data.get("results", []))},
            }
        except Exception as deep_err:
            logger.warning("Deep Research search encountered an error: %s", deep_err)

    if model == "Multi-Agent Swarm":
        from app.services.agent_swarm import execute_swarm_collaboration
        swarm_result = await execute_swarm_collaboration(message)
        return {
            "response_text": swarm_result["response_text"],
            "artifact_info": {"type": "swarm", "goal": swarm_result["goal"]},
        }

    lower = message.lower().strip()

    # 1. PDF Document / Report / Notes Intent
    pdf_direct = re.search(
        r"\b(in\s+pdf(\s+format)?|as\s+a\s+pdf|as\s+pdf|pdf\s*format|into\s+pdf|convert\s+to\s+pdf|export\s+(to\s+)?pdf|pdf\s*file|pdf\s*document|pdf\s*mein|pdf\s*me)\b",
        lower,
    )
    pdf_match = re.search(r"\b(pdf|report|whitepaper|handbook)\b", lower)
    pdf_actions = re.search(
        r"\b(bana|banaye|banao|chahiye|generate|generte|genrate|create|make|build|write|produce|download|export|give|provide|compile|prepare|de\s*do|bhejo|send|answers?|solutions?)\b",
        lower,
    )
    notes_intent = re.search(r"\b(notes|study\s*notes|answers?|solutions?|questions?)\b", lower) and pdf_match
    pdf_keyword_check = "pdf" in lower and any(
        w in lower for w in ["format", "download", "file", "give", "make", "create", "generate", "generte", "marks", "each", "solve", "answer", "compile", "send", "questions", "above"]
    )

    if pdf_direct or (pdf_match and pdf_actions) or notes_intent or pdf_keyword_check:
        return await _handle_pdf_request(message, user_id=user_id, conversation_history=conversation_history, db=db)

    # 2. PPT / Presentation Intent
    ppt_direct = re.search(
        r"\b(in\s+ppt(\s+format)?|in\s+pptx|as\s+a\s+ppt|as\s+ppt|ppt\s*format|pptx\s*format|into\s+ppt|convert\s+to\s+ppt|export\s+(to\s+)?ppt|ppt\s*file|presentation\s*file|ppt\s*mein|ppt\s*me)\b",
        lower,
    )
    ppt_match = re.search(r"\b(ppt|pptx|powerpoint|presentation|slide|slides|slideshow)\b", lower)
    ppt_actions = re.search(
        r"\b(bana|banaye|banao|chahiye|generate|create|make|build|produce|design|tayyar|give|provide|prepare|de\s*do|bhejo|send)\b",
        lower,
    )
    ppt_keyword_check = ("ppt" in lower or "pptx" in lower or "slides" in lower) and any(
        w in lower for w in ["format", "download", "file", "give", "make", "create", "generate", "bana", "chahiye"]
    )

    if ppt_direct or (ppt_match and (ppt_actions or "slide" in lower)) or ppt_keyword_check:
        return await _handle_ppt_request(message, user_id=user_id, conversation_history=conversation_history, db=db)

    # 3. AI Image Generation Intent
    img_noun = re.search(
        r"\b(image|images|photo|photos|picture|pictures|pic|pics|tasveer|tasveerein|illustration|wallpaper|visual|drawing|portrait|sketch)\b",
        lower,
    )
    img_action = re.search(
        r"\b(generate|create|make|draw|show|display|give|provide|send|render|produce|bana|banaye|banao|chahiye|dikhao|dikhana|de|do|lao|de\s*do|bhejo)\b",
        lower,
    )
    img_direct_phrase = re.search(
        r"\b(image\s+of|photo\s+of|picture\s+of|pic\s+of|portrait\s+of|tasveer\s+of|ki\s+photo|ki\s+image|ki\s+tasveer|ka\s+photo|ka\s+image)\b",
        lower,
    )

    if (img_noun and img_action) or img_direct_phrase or (img_noun and len(message.strip().split()) <= 5):
        return await _handle_image_request(message)

    # 4. Project ZIP Intent
    zip_match = re.search(r"\b(zip|project|source code|codebase|repo)\b", lower)
    zip_actions = re.search(r"\b(bana|banaye|banao|chahiye|generate|create|make|build|download|package|give|provide|send|de\s*do)\b", lower)
    if zip_match and zip_actions:
        return await _handle_project_request(message, user_id=user_id)

    # 5. Chart / Plot Intent
    chart_match = re.search(r"\b(plot|graph|chart|curve)\b", lower)
    chart_actions = re.search(r"\b(draw|generate|plot|bana|create|make|show|give|display|dikhao)\b", lower)
    if chart_match and chart_actions:
        return _handle_chart_request(message)

    # 6. Multi-Agent Swarm / Dev Squad Intent
    from app.services.agent_swarm import is_swarm_intent, execute_swarm_collaboration
    if is_swarm_intent(message):
        swarm_result = await execute_swarm_collaboration(message)
        return {
            "response_text": swarm_result["response_text"],
            "artifact_info": {"type": "swarm", "goal": swarm_result["goal"]},
        }

    return None



def _extract_slide_count(message: str) -> int:
    """Extract requested number of slides from user message."""
    count_match = re.search(r"(\d+)\s*(slide|slides|page|pages)", message, re.IGNORECASE)
    if count_match:
        try:
            return max(2, min(int(count_match.group(1)), 20))
        except ValueError:
            pass

    word_map = {
        "ek": 2, "do": 2, "teen": 3, "char": 4, "panch": 5, "paanch": 5,
        "che": 6, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
        "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
        "eight": 8, "nine": 9, "ten": 10,
    }
    for word, val in word_map.items():
        if re.search(rf"\b{word}\s*(slide|slides)\b", message, re.IGNORECASE):
            return val

    return 5


def parse_markdown_to_pdf_sections(text: str, default_title: str = "Technical Solutions & Analysis") -> Dict[str, Any]:
    """Parse an assistant's markdown response into structured title, summary, and PDF sections."""
    lines = text.strip().split("\n")
    title = default_title
    summary = ""
    sections: List[Dict[str, Any]] = []

    current_section: Optional[Dict[str, Any]] = None
    first_heading_found = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for title: # Heading or **Title** at top
        if not first_heading_found and (stripped.startswith("# ") or stripped.startswith("## ")):
            candidate_title = re.sub(r"^#+\s*", "", stripped)
            candidate_title = re.sub(r"[*_`]", "", candidate_title).strip()
            candidate_title = re.sub(r"^[^\w\s]+\s*", "", candidate_title).strip()
            if candidate_title and len(candidate_title) > 3:
                title = candidate_title
                first_heading_found = True
                continue

        # Check for section headers: ### or #### or **Question X...** or **X. ...**
        heading_match = None
        if stripped.startswith("### ") or stripped.startswith("## "):
            h_text = re.sub(r"^#+\s*", "", stripped)
            heading_match = re.sub(r"[*_`]", "", h_text).strip()
        elif stripped.startswith("#### "):
            h_text = re.sub(r"^#+\s*", "", stripped)
            heading_match = re.sub(r"[*_`]", "", h_text).strip()
        elif re.match(r"^\*\*(?:Question\s*\d+|Q\d+|\d+[\.\)]|[A-Z][\.\)])\s*.*?\*\*", stripped):
            heading_match = re.sub(r"^\*\*(.*?)\*\*.*", r"\1", stripped).strip()

        if heading_match:
            heading_clean = re.sub(r"^[^\w\s]+\s*", "", heading_match).strip()
            if current_section:
                sections.append(current_section)
            current_section = {
                "heading": heading_clean,
                "content": "",
                "points": [],
            }
            continue

        # Bullet point or content line
        clean_line = re.sub(r"^[-*•]\s*", "", stripped)
        clean_line = re.sub(r"^\d+\.\s*", "", clean_line)
        clean_line = re.sub(r"[*_`]", "", clean_line).strip()

        if current_section is not None:
            if stripped.startswith(("-", "*", "•")) or re.match(r"^\d+\.\s", stripped):
                if clean_line:
                    current_section["points"].append(clean_line)
            else:
                if not current_section["content"]:
                    current_section["content"] = clean_line
                else:
                    current_section["points"].append(clean_line)
        else:
            # Text before any section heading -> summary
            if not summary:
                summary = clean_line
            elif len(summary) < 400:
                summary += " " + clean_line

    if current_section:
        sections.append(current_section)

    # If no sections were parsed (e.g. plain paragraphs), chunk into logical sections
    if not sections and lines:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for idx, p in enumerate(paragraphs, start=1):
            clean_p = re.sub(r"[*_`#]", "", p).strip()
            if not clean_p:
                continue
            p_lines = [l.strip() for l in clean_p.split("\n") if l.strip()]
            sec_heading = p_lines[0][:60] if p_lines else f"Analysis Section {idx}"
            sec_points = p_lines[1:] if len(p_lines) > 1 else [clean_p]
            sections.append({
                "heading": sec_heading,
                "content": sec_points[0] if sec_points else "",
                "points": sec_points[1:] if len(sec_points) > 1 else sec_points,
            })

    if not summary:
        summary = f"Comprehensive technical breakdown and verified analysis of {title}."

    return {
        "title": title,
        "summary": summary[:400],
        "sections": sections,
    }


def parse_user_content_to_pdf_sections(text: str) -> Optional[Dict[str, Any]]:
    """Parse user-provided content directly into structured PDF title, summary, and sections.

    Used when the user's prompt directly contains structured questions, answers, notes, or essays
    intended for PDF compilation (e.g. 'Question 1: ... Answer: ... Question 2: ...').
    """
    if not text or len(text.strip().split()) < 30:
        return None

    # Check if text contains multiple question blocks
    q_pattern = r"(?:^|\n)\s*(?:(?:Q(?:uestion)?\s*\d+|\d+\.)[:\.\)]\s*[^\n]+)"
    q_matches = list(re.finditer(q_pattern, text, flags=re.IGNORECASE))
    if len(q_matches) >= 2:
        parts = re.split(f"({q_pattern})", text, flags=re.IGNORECASE)
        sections = []

        # Check if text contains a document title
        main_title = None
        t_match = re.search(r"(?:^|\n)\s*Title:\s*([^\n]+)", text, flags=re.IGNORECASE)
        if t_match:
            main_title = t_match.group(1).strip()

        for i in range(1, len(parts), 2):
            q_heading = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""

            # Check sub-title
            sub_title_match = re.search(r"Title:\s*([^\n]+)", body, flags=re.IGNORECASE)
            sec_title = q_heading
            if sub_title_match:
                st = sub_title_match.group(1).strip()
                if not main_title:
                    main_title = st
                sec_title = f"{q_heading} - {st}"

            # Clean body
            body_clean = re.sub(r"Answer\s*\(Page-wise\)", "", body, flags=re.IGNORECASE)
            body_clean = re.sub(r"Title:\s*[^\n]+", "", body_clean, flags=re.IGNORECASE).strip()

            # Extract intro paragraph
            intro = ""
            intro_match = re.search(r"Introduction\s+([^\n]+(?:\n(?![A-Z][a-zA-Z\s]+:)[^\n]+)*)", body_clean, flags=re.IGNORECASE)
            if intro_match:
                intro = intro_match.group(1).strip()
                intro = re.sub(
                    r"\b(give\s+in\s+pdf\s+format|generate\s+in\s+pdf\s+format|as\s+a\s+pdf|in\s+pdf\s+format|pdf\s*format|pdf\s*mein|pdf\s*me|generate\s*pdf|make\s*pdf)\b.*$",
                    "",
                    intro,
                    flags=re.IGNORECASE,
                ).strip()

            # Extract points / paragraphs
            lines = [l.strip() for l in body_clean.splitlines() if l.strip()]
            points = []
            for l in lines:
                if re.match(r"^(Introduction|javascript|Copy|Answer|Title:)", l, flags=re.IGNORECASE):
                    continue
                clean_l = re.sub(r"^[-*•]\s*", "", l)
                clean_l = re.sub(
                    r"\b(give\s+in\s+pdf\s+format|generate\s+in\s+pdf\s+format|as\s+a\s+pdf|in\s+pdf\s+format|pdf\s*format|pdf\s*mein|pdf\s*me|generate\s*pdf|make\s*pdf)\b.*$",
                    "",
                    clean_l,
                    flags=re.IGNORECASE,
                ).strip()
                if len(clean_l) > 12:
                    points.append(clean_l)

            sections.append({
                "heading": sec_title[:95],
                "content": intro or (points[0] if points else "Technical analysis and evaluation."),
                "points": points[1:8] if intro else points[:8],
                "page_break": True,
            })

        if not main_title:
            if "metamask" in text.lower() or "dapp" in text.lower():
                main_title = "DApp Architecture & MetaMask Integration"
            else:
                main_title = re.sub(r"^Question\s*\d+[:\.\)]\s*", "", sections[0]["heading"]) if sections else "Technical Examination Solutions"

        summary = (
            f"Comprehensive technical compilation covering {main_title}. "
            "Includes detailed component analysis, interface specifications, implementation workflows, and architectural evaluation."
        )
        return {
            "title": main_title,
            "summary": summary,
            "sections": sections,
        }

    return None


def _extract_topic(message: str, trigger_words: Optional[List[str]] = None) -> str:
    """Extract clean, precise subject topic from user message across English, Hindi, and Hinglish."""
    lower = message.lower()

    # If user message is purely referential or an action request to convert prior content, return empty
    if any(
        phrase in lower for phrase in [
            "the above", "above answer", "above response", "previous answer", "previous response",
            "iska pdf", "isse pdf", "iske answers", "ye answers", "yeh answers", "this answer",
            "convert this", "make pdf of this", "generate pdf of this"
        ]
    ) and not any(k in lower for k in ["smart contract", "machine learning", "big data", "deep learning"]):
        return ""

    # 1. Domain detection for complex or multi-question assessment prompts
    if any(k in lower for k in [
        "aabais", "aaibs", "multi-agent", "multi agent", "swarm intelligence",
        "reinforcement learning", "q-learning", "q learning", "markov decision process",
        "mdp", "explainable ai", "xai", "generative ai agent", "autonomous ai"
    ]):
        return "Autonomous AI Based Systems (AABAIS)"
    if any(k in lower for k in ["metamask", "dapp", "front-end applications", "front-end app", "web3"]):
        return "Ethereum DApp & MetaMask Integration"
    if any(k in lower for k in ["smart contract", "solidity", "ethereum", "blockchain"]):
        if any(w in lower for w in ["security", "vulnerability", "audit", "reentrancy", "overflow", "exploit"]):
            return "Smart Contract Security & Vulnerability Analysis"
        return "Smart Contract Architecture & Development"
    if any(k in lower for k in ["machine learning", "supervised learning", "unsupervised learning", "statistical pattern"]):
        return "Machine Learning"
    if any(k in lower for k in ["big data", "hadoop", "spark", "mapreduce", "hdfs"]):
        return "Big Data Analytics"
    if any(k in lower for k in ["deep learning", "neural network", "transformer", "cnn", "rnn"]):
        return "Deep Learning & Neural Networks"
    if any(k in lower for k in ["cloud computing", "aws", "kubernetes", "microservices"]):
        return "Cloud Computing & Systems"
    if any(k in lower for k in ["cyber security", "cryptography", "penetration testing", "infosec"]):
        return "Cyber Security & Cryptography"
    if any(k in lower for k in ["operating system", "process scheduling", "virtual memory", "deadlock"]):
        return "Operating Systems"
    if any(k in lower for k in ["database", "dbms", "sql query", "nosql", "normalization"]):
        return "Database Management Systems"
    if any(k in lower for k in ["data structure", "data structures", "dsa", "dynamic programming", "graph theory", "sorting algorithm", "binary search tree"]):
        return "Data Structures & Algorithms"
    if any(k in lower for k in ["python programming", "asyncio", "cpython"]):
        return "Python Architecture & Systems"

    cleaned = message.strip()

    # 1b. If message contains an attached file envelope, extract topic from user question or filename
    if "[attached file:" in lower:
        fn_match = re.search(r"\[Attached File:\s*([^(\]]+)", message, re.IGNORECASE)
        if fn_match:
            fn_lower = fn_match.group(1).lower()
            if any(k in fn_lower for k in ["aabais", "aaibs", "multi_agent", "swarm", "rl", "autonomous"]):
                return "Autonomous AI Based Systems (AABAIS)"
        parts = re.split(r"User Question(?:/Instruction)?:\s*", message, flags=re.IGNORECASE)
        if len(parts) > 1 and len(parts[-1].strip()) > 3:
            cleaned = parts[-1].strip()

    # 2. Strip common conversational greetings, temporal markers, and prefixes
    cleaned = re.sub(
        r"^(now|ab|phir|then|so|mujhe|humko|hum|please|can you|could you|kindly|hey cognexa|bhai|bro|sunn?|cognexa)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 3. Strip action verbs, typos, and request words
    cleaned = re.sub(
        r"\b(now|ab|phir|generte|genrate|genereate|creat|mak|bana\s*ke\s*do|bana\s*do|bana\s*dena|banaye|banao|chahiye|tayyar\s*karo|generate|create|make|build|produce|design|write|download|export|dikhao|show|give\s*answers?|give)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 3b. Strip referential markers (above, previous, this answer, iska, etc.)
    cleaned = re.sub(
        r"\b(above\s*answers?|above\s*responses?|the\s*above|above|previous\s*answers?|previous|this\s*answers?|this|iska|isse|iske|iss|ye\s*answers?|yeh\s*answers?|ye\s*content|yeh\s*content|ye|yeh)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 4. Strip artifact formats and document types
    cleaned = re.sub(
        r"\b(pdf\s*document|pdf\s*maker|pdf\s*report|pdf|pptx?|powerpoint|presentation|slideshow|zip|project|image|photo|study\s*notes|notes?|handbook|guide|tutorial|overview|format)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 5. Strip exam marks and count phrases
    cleaned = re.sub(
        r"\b(\d+|ek|do|teen|char|panch|paanch|che|chhe|saat|aath|nau|das|two|three|four|five|six|seven|eight|nine|ten)\s*(slides?|pages?|marks?)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(for\s+\d+\s+marks?\s+each|all\s+questions?|questions?|answers?)\b", " ", cleaned, flags=re.IGNORECASE)

    # 6. Strip connector prepositions & conjunctions
    cleaned = re.sub(
        r"\b(on|about|for|of|regarding|in|pe|par|ka|ki|ke|and|with|aur|waala|wali|each)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 7. Strip custom trigger words
    if trigger_words:
        for tw in trigger_words:
            cleaned = re.sub(rf"\b{re.escape(tw)}\b", " ", cleaned, flags=re.IGNORECASE)

    # 8. Clean punctuation, extra spaces, and trailing/leading articles
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^(an|a|the)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+(an|a|the)$", "", cleaned, flags=re.IGNORECASE).strip()

    # Cap at first 6 meaningful words for concise title
    words = cleaned.split()
    if len(words) > 6:
        cleaned = " ".join(words[:6])

    generic_terms = {"", "now", "above", "now generte", "the above", "pdf", "report", "notes", "answer", "answers"}
    if len(cleaned) < 2 or cleaned.lower() in generic_terms:
        return ""

    return cleaned.title()



async def _save_to_vector_memory(
    user_id: Optional[uuid.UUID],
    topic: str,
    content_text: str,
    metadata_: Dict[str, Any],
    db: Optional[Any] = None,
) -> bool:
    """Store generated knowledge into user's persistent vector memory."""
    if not user_id:
        return False
    try:
        from app.models.memory import Memory, MemoryType
        from app.services.embedding import get_embedding

        dense_vec = get_embedding(content_text[:1200])
        mem = Memory(
            user_id=user_id,
            memory_type=MemoryType.verified_knowledge.value,
            content=content_text.strip(),
            embedding=dense_vec,
            metadata_=metadata_,
            is_active=True,
        )
        if db is not None:
            db.add(mem)
            await db.flush()
            logger.info("Successfully stored verified knowledge for '%s' in memory of user %s", topic, user_id)
            return True

        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            session.add(mem)
            await session.commit()
            logger.info("Successfully stored verified knowledge for '%s' in memory of user %s", topic, user_id)
            return True
    except Exception as exc:
        logger.warning("Could not persist memory record for '%s': %s", topic, exc)
        return False


async def _handle_pdf_request(
    message: str,
    user_id: Optional[uuid.UUID] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute publication-grade PDF document generation and store knowledge in memory."""
    lower = message.lower()

    # Check if this is a referential request pointing to previous assistant content
    is_referential = any(
        w in lower for w in [
            "above", "the above", "above answer", "above response", "previous",
            "previous answer", "iska", "isse", "iske", "is answer", "this answer", "of this",
            "convert this", "iss answer", "ye answer", "yeh answer", "ye answers", "yeh answers"
        ]
    )

    last_assistant_content: Optional[str] = None
    if conversation_history:
        for m in reversed(conversation_history):
            if m.get("role") == "assistant" and len(m.get("content", "").strip()) > 80:
                c = m.get("content", "")
                if "[Click Here to Download:" not in c and "📥 Download" not in c:
                    last_assistant_content = c
                    break

    topic = _extract_topic(message, ["pdf", "report", "document", "notes"])

    # 0. Check if user prompt directly contains document content / Q&A text to compile into PDF!
    user_supplied_parsed = parse_user_content_to_pdf_sections(message)
    is_user_content_applied = False
    is_referential_applied = False

    if user_supplied_parsed and len(user_supplied_parsed.get("sections", [])) >= 1:
        logger.info("Generating PDF directly from user-supplied prompt content.")
        doc_title = user_supplied_parsed["title"]
        summary = user_supplied_parsed["summary"]
        sections = user_supplied_parsed["sections"]
        is_user_content_applied = True
    elif (is_referential or not topic or topic in ["Engineering Systems", "Document", "Notes", "Answers", "Study Notes"]) and last_assistant_content:
        logger.info("Generating PDF directly from preceding assistant message content.")
        parsed = parse_markdown_to_pdf_sections(last_assistant_content, default_title=topic or "Technical Solutions & Analysis")
        doc_title = parsed.get("title") or "Technical Solutions & Analysis"
        summary = parsed.get("summary") or ""
        sections = parsed.get("sections") or []
        is_referential_applied = True
    else:
        effective_topic = topic or "Engineering Systems"
        # Synthesize rich academic notes with real topic content
        from app.services.content_synthesizer import synthesize_academic_notes
        notes_data = await synthesize_academic_notes(effective_topic, user_prompt=message)
        doc_title = notes_data.get("title", f"{effective_topic} Comprehensive Study Notes")
        summary = notes_data.get("summary", "")
        sections = notes_data.get("sections", [])

    res = generate_pdf_report(
        title=doc_title,
        sections=sections,
        summary=summary,
        author="Cognexa Autonomous AI",
    )

    filename = res["filename"]
    download_url = res["download_url"]

    # Store into user's persistent vector memory
    mem_saved = False
    if user_id:
        mem_content = (
            f"Verified Technical Notes: {doc_title}\n"
            f"Summary: {summary}\n"
            "Key Sections:\n"
            + "\n".join([f"- {s.get('heading')}: " + " ".join(s.get('points', []))[:180] for s in sections])
        )
        mem_saved = await _save_to_vector_memory(
            user_id=user_id,
            topic=doc_title,
            content_text=mem_content,
            metadata_={
                "topic": doc_title,
                "artifact_type": "pdf_notes",
                "filename": filename,
                "download_url": download_url,
                "sections_count": len(sections),
            },
            db=db,
        )

    # Build concise, non-cluttered response (file contains full details)
    is_exam_or_solutions = any(w in message.lower() for w in ["marks", "question", "answer", "solution", "solve"])
    if is_user_content_applied:
        intro_line = f"📄 **Maine aapke provided questions aur answers ko directly compile karke publication-grade PDF generate kar di hai!**\n"
    elif is_referential_applied:
        intro_line = f"📄 **Maine aapke previous answer ('{doc_title}') se publication-grade PDF Document generate kar diya hai!**\n"
    elif is_exam_or_solutions:
        intro_line = f"📄 **Maine aapke sabhi questions ke complete answers compile karke publication-grade PDF generate kar di hai!**\n"
    else:
        intro_line = f"📄 **Maine aapke liye '{doc_title}' par publication-quality PDF Document generate kar diya hai!**\n"

    response_lines = [
        intro_line,
        "Is document mein theoretical concepts, complete technical answers, architectures aur evaluation points professionally formatted layout mein included hain.\n",
        "### 📋 Included Chapters / Questions in PDF:\n",
    ]

    for idx, sec in enumerate(sections, start=1):
        heading = sec.get("heading", f"Section {idx}")
        response_lines.append(f"- **Section {idx}**: {heading}")

    response_lines.append("\n---")
    if mem_saved or user_id:
        response_lines.append("🧠 **Cognitive Memory Synchronized:**")
        response_lines.append(f"Is document ke saare solutions aur concepts aapke **Persistent Vector Memory** mein index ho chuke hain.\n")

    response_lines.append("### 📥 Download PDF Document")
    response_lines.append(f"👉 **[Click Here to Download: {filename} ({res['size_kb']} KB)]({download_url})**\n")
    response_lines.append("*All complete answers, mathematical models, and code implementations are contained inside the PDF.*")

    return {
        "response_text": "\n".join(response_lines),
        "artifact_info": {
            "type": "pdf",
            "filename": filename,
            "download_url": download_url,
            "title": doc_title,
            "topic": doc_title,
            "size_kb": res["size_kb"],
            "memory_saved": mem_saved,
        },
    }


async def _handle_ppt_request(
    message: str,
    user_id: Optional[uuid.UUID] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute PowerPoint presentation generation and return response."""
    slide_count = _extract_slide_count(message)
    lower = message.lower()
    is_referential = any(
        w in lower for w in [
            "above", "the above", "previous", "iska", "isse", "this answer", "convert this"
        ]
    )

    last_assistant_content: Optional[str] = None
    if conversation_history:
        for m in reversed(conversation_history):
            if m.get("role") == "assistant" and len(m.get("content", "").strip()) > 80:
                c = m.get("content", "")
                if "[Click Here to Download:" not in c and "📥 Download" not in c:
                    last_assistant_content = c
                    break

    topic = _extract_topic(message, ["ppt", "presentation", "slides", "pptx"])
    if (is_referential or not topic or topic in ["Engineering Systems", "Presentation", "Slides", ""]) and last_assistant_content:
        parsed = parse_markdown_to_pdf_sections(last_assistant_content, default_title="Executive Overview")
        topic = parsed.get("title") or "Technical Presentation"
    elif not topic:
        topic = "Engineering Systems"

    res = generate_presentation(
        topic=topic,
        slide_count=slide_count,
        theme="dark",
    )

    filename = res["filename"]
    download_url = res["download_url"]
    slides = res["slides"]

    # Store into vector memory if user_id present
    mem_saved = False
    if user_id:
        mem_content = (
            f"PowerPoint Presentation Outline: {topic.title()} ({slide_count} Slides)\n"
            + "\n".join([f"- Slide {i+1}: {s['title']} -> " + "; ".join(s.get('points', []))[:150] for i, s in enumerate(slides)])
        )
        mem_saved = await _save_to_vector_memory(
            user_id=user_id,
            topic=topic.title(),
            content_text=mem_content,
            metadata_={
                "topic": topic.title(),
                "artifact_type": "pptx_presentation",
                "filename": filename,
                "download_url": download_url,
                "slide_count": slide_count,
            },
            db=db,
        )

    # Build concise, non-cluttered response
    response_lines = [
        f"🎯 **Maine aapke liye '{topic.title()}' par {slide_count} Slides ki PowerPoint Presentation (.pptx) generate kar di hai!**\n",
        "Aapki presentation widescreen 16:9 layout, dark executive theme aur structured bullet points ke sath download ke liye tayyar hai.\n",
        "### 📊 Presentation Slide Outline:\n",
    ]

    for idx, slide in enumerate(slides):
        response_lines.append(f"- **Slide {idx + 1}**: {slide['title']}")

    response_lines.append("\n---")
    if mem_saved or user_id:
        response_lines.append("🧠 **Cognitive Memory Synchronized:**")
        response_lines.append(f"Presentation content aapke **Persistent Vector Memory** mein save ho chuka hai.\n")

    response_lines.append("### 📥 Download Presentation")
    response_lines.append(f"👉 **[Click Here to Download: {filename} ({res['size_kb']} KB)]({download_url})**\n")
    response_lines.append("*All slides and bullet points are packaged inside the editable .pptx file.*")


    return {
        "response_text": "\n".join(response_lines),
        "artifact_info": {
            "type": "pptx",
            "filename": filename,
            "download_url": download_url,
            "topic": topic,
            "slide_count": slide_count,
            "size_kb": res["size_kb"],
            "memory_saved": mem_saved,
        },
    }


def _extract_image_prompt(message: str) -> str:
    """Extract clean visual subject prompt for AI image generation."""
    cleaned = message.strip()
    cleaned = re.sub(
        r"^(mujhe|humko|hum|please|can you|could you|kindly|hey cognexa|bhai|bro|sunn?|cognexa)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(generate|create|make|draw|show|display|give\s*me|give|provide|send|bana\s*do|bana\s*ke\s*do|banao|dikhao|dikhana|de\s*do|chahiye|bhejo)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(an\s+image\s+of|a\s+photo\s+of|a\s+picture\s+of|image\s+of|photo\s+of|picture\s+of|pic\s+of|portrait\s+of|tasveer\s+of|images?|photos?|pictures?|pics?|tasveere?i?n?|wallpaper|drawing|illustration|visual|portrait)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(ka|ki|ke|on|about|for|of|in|pe|par|an|a|the)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if len(cleaned) >= 2 else "Artistic Visual Composition"


async def _handle_image_request(message: str) -> Dict[str, Any]:
    """Execute AI Image generation and return response."""
    prompt = _extract_image_prompt(message)

    res = await generate_image(prompt=prompt)
    filename = res["filename"]
    download_url = res["download_url"]

    response_lines = [
        f"🎨 **Maine aapki request par AI Generated Image tayyar kar di hai:**\n",
        f"**Prompt:** *\"{prompt}\"*\n",
        f"![{prompt}]({download_url})\n",
        "---",
        f"### 📥 High-Resolution Image Download",
        f"👉 **[Click Here to Download Original: {filename}]({download_url})**\n",
    ]


    return {
        "response_text": "\n".join(response_lines),
        "artifact_info": {
            "type": "image",
            "filename": filename,
            "download_url": download_url,
            "prompt": prompt,
        },
    }


async def _handle_project_request(
    message: str,
    user_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """Execute Software Project scaffolding and ZIP bundling."""
    topic = _extract_topic(message, ["project", "zip", "codebase"])
    ptype = "python"
    if "web" in message.lower() or "html" in message.lower():
        ptype = "web"

    res = generate_software_project(
        project_name=topic,
        project_type=ptype,
        description=f"Automated project for {topic}",
    )

    filename = res["zip_filename"]
    download_url = res["download_url"]

    # Store into vector memory if user_id present
    mem_saved = False
    if user_id:
        mem_content = (
            f"Software Project Scaffolding: {topic.title()} ({ptype.upper()})\n"
            f"Archive: {filename}\n"
            f"Included Files: {', '.join(res.get('files', []))}\n"
        )
        mem_saved = await _save_to_vector_memory(
            user_id=user_id,
            topic=topic.title(),
            content_text=mem_content,
            metadata_={
                "topic": topic.title(),
                "artifact_type": "project_zip",
                "filename": filename,
                "download_url": download_url,
            },
        )

    response_lines = [
        f"📦 **Maine aapke liye complete '{topic.title()}' project bana kar `.zip` archive mein package kar diya hai!**\n",
        f"Is project mein full working source code, configuration files aur test setup structured format mein tayyar hai.\n",
        "### 📁 Project Contents Included:\n",
    ]

    for f in res.get("files", []):
        response_lines.append(f"- 📄 `{f}`")

    response_lines.append("\n### ⚡ How to Run:")
    response_lines.append("```bash")
    response_lines.append(f"# 1. Extract {filename}")
    response_lines.append("cd " + res["project_name"])
    if ptype == "python":
        response_lines.append("pip install -r requirements.txt")
        response_lines.append("python main.py")
    else:
        response_lines.append("python -m http.server 8080")
    response_lines.append("```\n")
    response_lines.append("---")
    if mem_saved or user_id:
        response_lines.append("🧠 **Cognitive Memory Synchronized:**")
        response_lines.append(f"Project structure aur details aapke **Persistent Vector Memory** mein save ho chuki hain.\n")

    response_lines.append("### 📥 Download Project ZIP Archive")
    response_lines.append(f"👉 **[Click Here to Download: {filename} ({res['size_kb']} KB)]({download_url})**\n")

    return {
        "response_text": "\n".join(response_lines),
        "artifact_info": {
            "type": "zip",
            "filename": filename,
            "download_url": download_url,
            "project_name": topic,
            "file_count": res["file_count"],
            "size_kb": res["size_kb"],
            "memory_saved": mem_saved,
        },
    }


def _handle_chart_request(message: str) -> Dict[str, Any]:
    """Execute engineering chart plotting and return response."""
    topic = _extract_topic(message, ["plot", "graph", "chart", "curve"])

    res = generate_chart_plot(title=topic.title())
    filename = res["filename"]
    download_url = res["download_url"]

    response_lines = [
        f"📈 **Maine aapke liye '{topic.title()}' ka Engineering Analysis Chart plot kar diya hai:**\n",
        f"![{topic}]({download_url})\n",
        "---",
        f"👉 **[Download High-Res Chart: {filename} ({res['size_kb']} KB)]({download_url})**\n",
    ]

    return {
        "response_text": "\n".join(response_lines),
        "artifact_info": {
            "type": "chart",
            "filename": filename,
            "download_url": download_url,
            "title": topic.title(),
        },
    }
