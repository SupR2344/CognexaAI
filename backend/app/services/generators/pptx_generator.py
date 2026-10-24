"""PowerPoint Presentation (.pptx) Generator for Cognexa AI.

Creates professionally styled multi-slide presentations with modern layouts,
executive dark/light color schemes, structured bullet points, and speaker notes.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("exports").resolve()
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_presentation(
    topic: str,
    slide_count: int = 5,
    custom_content: Optional[str] = None,
    theme: str = "dark",
) -> Dict[str, Any]:
    """Generate a real PowerPoint (.pptx) presentation.

    Args:
        topic: Presentation subject or title.
        slide_count: Number of slides (clamped between 2 and 20).
        custom_content: Optional specific content/points provided by user.
        theme: 'dark' (navy/cyan gradient tech) or 'light' (clean modern executive).

    Returns:
        Dict with status, filename, slide_count, download_url, slides summary.
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.enum.shapes import MSO_SHAPE
    except ImportError:
        logger.error("python-pptx is not installed.")
        raise RuntimeError("python-pptx library is required for PPT generation.")

    slide_count = max(2, min(slide_count, 20))
    prs = Presentation()
    prs.slide_width = Inches(13.333)  # 16:9 widescreen
    prs.slide_height = Inches(7.5)

    # Theme colors
    if theme == "dark":
        bg_rgb = RGBColor(15, 23, 42)        # Slate 900
        card_rgb = RGBColor(30, 41, 59)      # Slate 800
        accent_rgb = RGBColor(0, 210, 255)   # Electric Cyan
        purple_rgb = RGBColor(123, 47, 247)  # Purple
        text_primary = RGBColor(248, 250, 252) # White
        text_secondary = RGBColor(148, 163, 184) # Slate 400
    else:
        bg_rgb = RGBColor(248, 250, 252)
        card_rgb = RGBColor(255, 255, 255)
        accent_rgb = RGBColor(37, 99, 235)   # Blue 600
        purple_rgb = RGBColor(109, 40, 217)
        text_primary = RGBColor(15, 23, 42)
        text_secondary = RGBColor(71, 85, 105)

    # Build outline of slides
    slides_data = _generate_slide_outline(topic, slide_count, custom_content)

    blank_layout = prs.slide_layouts[6]  # Completely blank slide layout for custom styling

    for i, s_info in enumerate(slides_data):
        slide = prs.slides.add_slide(blank_layout)

        # 1. Full slide background shape
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = bg_rgb
        bg.line.fill.background()

        if i == 0:
            # === Title Slide ===
            # Accent banner top
            banner = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(1), Inches(1), Inches(11.333), Inches(0.1)
            )
            banner.fill.solid()
            banner.fill.fore_color.rgb = accent_rgb
            banner.line.fill.background()

            # Title card container
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(1.8), Inches(11.333), Inches(4.5)
            )
            card.fill.solid()
            card.fill.fore_color.rgb = card_rgb
            card.line.color.rgb = accent_rgb
            card.line.width = Pt(1.5)

            # Title text
            txBox = slide.shapes.add_textbox(Inches(1.5), Inches(2.2), Inches(10.333), Inches(2.0))
            tf = txBox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = s_info["title"]
            p.font.size = Pt(40)
            p.font.bold = True
            p.font.color.rgb = text_primary
            p.alignment = PP_ALIGN.LEFT

            # Subtitle
            p2 = tf.add_paragraph()
            p2.text = s_info.get("subtitle", f"Comprehensive Overview & Analysis • Cognexa AI Engine")
            p2.font.size = Pt(20)
            p2.font.color.rgb = accent_rgb
            p2.space_before = Pt(14)

            # Metadata footer inside title
            p3 = tf.add_paragraph()
            p3.text = f"Prepared by Cognexa Autonomous Intelligence • {slide_count} Slides"
            p3.font.size = Pt(13)
            p3.font.color.rgb = text_secondary
            p3.space_before = Pt(24)

        else:
            # === Content Slide ===
            # Slide Header Card
            header_card = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.6), Inches(11.733), Inches(1.1)
            )
            header_card.fill.solid()
            header_card.fill.fore_color.rgb = card_rgb
            header_card.line.fill.background()

            # Accent pill indicator
            pill = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(0.6), Inches(0.15), Inches(1.1)
            )
            pill.fill.solid()
            pill.fill.fore_color.rgb = accent_rgb
            pill.line.fill.background()

            # Slide Number Badge
            num_box = slide.shapes.add_textbox(Inches(11.2), Inches(0.8), Inches(1.2), Inches(0.6))
            num_tf = num_box.text_frame
            np = num_tf.paragraphs[0]
            np.text = f"0{i+1}" if (i+1) < 10 else f"{i+1}"
            np.font.size = Pt(22)
            np.font.bold = True
            np.font.color.rgb = accent_rgb

            # Slide Title text
            htx = slide.shapes.add_textbox(Inches(1.2), Inches(0.8), Inches(9.8), Inches(0.7))
            htf = htx.text_frame
            htf.word_wrap = True
            hp = htf.paragraphs[0]
            hp.text = s_info["title"]
            hp.font.size = Pt(26)
            hp.font.bold = True
            hp.font.color.rgb = text_primary

            # Main Content Card
            content_card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.0), Inches(11.733), Inches(4.7)
            )
            content_card.fill.solid()
            content_card.fill.fore_color.rgb = card_rgb
            content_card.line.color.rgb = RGBColor(45, 60, 90)
            content_card.line.width = Pt(1)

            # Bullet points textbox
            ctx = slide.shapes.add_textbox(Inches(1.3), Inches(2.3), Inches(10.7), Inches(4.0))
            ctf = ctx.text_frame
            ctf.word_wrap = True

            points = s_info.get("points", [])
            for p_idx, pt in enumerate(points):
                bp = ctf.paragraphs[0] if p_idx == 0 else ctf.add_paragraph()
                bp.text = f"•  {pt}"
                bp.font.size = Pt(18)
                bp.font.color.rgb = text_primary
                bp.space_before = Pt(14)
                bp.space_after = Pt(4)

        # Footer
        ftx = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.733), Inches(0.4))
        ftf = ftx.text_frame
        fp = ftf.paragraphs[0]
        fp.text = f"Cognexa Engineering Suite  |  {topic}  |  Slide {i+1} of {slide_count}"
        fp.font.size = Pt(10)
        fp.font.color.rgb = text_secondary

    # Sanitize filename
    clean_topic = re.sub(r"[^a-zA-Z0-9_\-\s]", "", topic).strip()
    clean_topic = re.sub(r"\s+", "_", clean_topic)[:40] or "Presentation"
    unique_suffix = uuid.uuid4().hex[:6]
    filename = f"{clean_topic}_{unique_suffix}.pptx"
    out_path = EXPORTS_DIR / filename
    prs.save(str(out_path))

    file_size_kb = round(out_path.stat().st_size / 1024, 1)
    download_url = f"http://localhost:8001/downloads/{filename}"

    logger.info("Generated PowerPoint presentation: %s (%s KB, %s slides)", filename, file_size_kb, slide_count)

    return {
        "status": "success",
        "filename": filename,
        "topic": topic,
        "slide_count": slide_count,
        "size_kb": file_size_kb,
        "download_url": download_url,
        "slides": slides_data,
    }


def _generate_slide_outline(
    topic: str, slide_count: int, custom_content: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Generate structured content and bullet points for each slide based on topic."""
    slides: List[Dict[str, Any]] = []

    # Parse custom content if user provided specific points
    custom_lines = [
        l.strip().lstrip("-*•0123456789. ")
        for l in (custom_content or "").split("\n")
        if l.strip()
    ]

    # Slide 1: Title
    slides.append({
        "title": topic.title(),
        "subtitle": "Architectural Overview & Core Fundamentals",
        "points": [],
    })

    # Check if curated curriculum is available for topic
    from app.services.content_synthesizer import _match_curated_knowledge
    curated = _match_curated_knowledge(topic)

    if curated and curated.get("sections"):
        needed_content_slides = slide_count - 1
        cur_sections = curated["sections"]
        for s_idx in range(needed_content_slides):
            if s_idx < len(cur_sections):
                sec = cur_sections[s_idx]
                title = sec.get("heading", f"Key Concept {s_idx + 1}")
                points = [p[:130] for p in sec.get("points", [])[:4]]
                if not points and sec.get("content"):
                    points = [sec["content"][:130]]
            else:
                title = f"{topic}: Advanced Analysis Part {s_idx + 1}"
                points = [
                    f"Specialized evaluation of {topic} architecture components.",
                    "Latency vs throughput optimization benchmarks.",
                    "Operational security and disaster recovery protocols.",
                    "Production best practices and verified recommendations.",
                ]
            if custom_lines:
                chunk = custom_lines[s_idx * 3 : (s_idx + 1) * 3]
                if chunk:
                    points = chunk + points[len(chunk):]
            slides.append({"title": title, "points": points})
        return slides

    # Standard presentation structure templates
    default_structure = [
        (
            f"Introduction to {topic}",
            [
                f"Understanding the core principles and context of {topic}.",
                "Key motivators driving modern industry and research adoption.",
                "Primary objectives and baseline problem statements addressed.",
                "High-level ecosystem overview and technological evolution.",
            ],
        ),
        (
            "Core Architecture & Foundations",
            [
                "Fundamental building blocks and modular layer design.",
                "Data pipeline, protocol interfaces, and state synchronization.",
                "Security boundaries, fault tolerance, and resilience mechanisms.",
                "Performance benchmarks and latency profiling metrics.",
            ],
        ),
        (
            "Key Advantages & Capabilities",
            [
                "Scalability: Horizontal expansion with predictable throughput.",
                "Efficiency: Optimized resource utilization and execution overhead.",
                "Reliability: Self-healing architectures and automated failovers.",
                "Interoperability: Seamless integration with modern cloud stacks.",
            ],
        ),
        (
            "Real-World Use Cases & Applications",
            [
                "Enterprise deployments across distributed microservices.",
                "Automated analytical pipelines and real-time processing.",
                "Edge computing, IoT nodes, and low-latency environments.",
                "Case studies demonstrating high ROI and operational gains.",
            ],
        ),
        (
            "Implementation Strategy & Roadmap",
            [
                "Phase 1: Environment provisioning and dependency auditing.",
                "Phase 2: Core service implementation and automated test suites.",
                "Phase 3: Staging deployment, load testing, and security verification.",
                "Phase 4: Production rollout and continuous telemetry monitoring.",
            ],
        ),
        (
            "Future Outlook & Conclusion",
            [
                "Emerging trends shaping next-generation developments.",
                "Integration with artificial intelligence and autonomous workflows.",
                "Strategic recommendations for organizations and developers.",
                "Open questions, community contributions, and Q&A session.",
            ],
        ),
    ]

    needed_content_slides = slide_count - 1
    for s_idx in range(needed_content_slides):
        if s_idx < len(default_structure):
            title, points = default_structure[s_idx]
        else:
            title = f"{topic}: Deep Dive Analysis Part {s_idx + 1}"
            points = [
                f"Detailed inspection of component #{s_idx + 1} characteristics.",
                "Trade-off analysis: latency vs throughput considerations.",
                "Operational playbooks and maintenance guidelines.",
                "Best practices derived from production telemetry.",
            ]

        # Blend user custom content if available
        if custom_lines:
            chunk = custom_lines[s_idx * 3 : (s_idx + 1) * 3]
            if chunk:
                points = chunk + points[len(chunk):]

        slides.append({"title": title, "points": points})

    return slides

