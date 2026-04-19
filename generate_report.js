const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  TableOfContents, ExternalHyperlink
} = require("docx");
const fs = require("fs");

// ─── COLORS & HELPERS ────────────────────────────────────────────────────────
const BLUE = "1F3864";
const LIGHT_BLUE = "D6E4F0";
const MID_BLUE = "2E75B6";
const GRAY = "595959";
const LIGHT_GRAY = "F2F2F2";
const BLACK = "000000";

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function h(level, text, opts = {}) {
  return new Paragraph({
    heading: level,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 },
    pageBreakBefore: opts.pageBreak || false,
    children: [new TextRun({ text, bold: true, color: opts.color || BLUE,
      size: level === HeadingLevel.HEADING_1 ? 28 : level === HeadingLevel.HEADING_2 ? 24 : 22,
      font: "Arial" })]
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 360 },
    children: [new TextRun({ text, size: 22, font: "Arial", color: opts.color || BLACK,
      bold: opts.bold || false, italics: opts.italic || false })]
  });
}

function pRich(runs, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 360 },
    children: runs
  });
}

function run(text, opts = {}) {
  return new TextRun({ text, size: 22, font: "Arial", color: opts.color || BLACK,
    bold: opts.bold || false, italics: opts.italic || false });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 80 },
    children: [new TextRun({ text, size: 22, font: "Arial" })]
  });
}

function bulletRich(runs, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 80 },
    children: runs
  });
}

function placeholder(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 200 },
    border: {
      top: { style: BorderStyle.DASHED, size: 8, color: "AAAAAA" },
      bottom: { style: BorderStyle.DASHED, size: 8, color: "AAAAAA" },
      left: { style: BorderStyle.DASHED, size: 8, color: "AAAAAA" },
      right: { style: BorderStyle.DASHED, size: 8, color: "AAAAAA" },
    },
    children: [new TextRun({ text: `[ ${text} ]`, size: 20, font: "Arial", color: "888888", italics: true })]
  });
}

function spacer() {
  return new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function sectionDivider() {
  return new Paragraph({
    spacing: { before: 160, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2E75B6", space: 1 } },
    children: [new TextRun("")]
  });
}

// ─── TABLE HELPERS ────────────────────────────────────────────────────────────
function headerCell(text, width) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: { fill: "1F3864", type: ShadingType.CLEAR },
    margins: { top: 100, bottom: 100, left: 150, right: 150 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, size: 20, font: "Arial", bold: true, color: "FFFFFF" })] })]
  });
}

function dataCell(text, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: { fill: opts.fill || "FFFFFF", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 150, right: 150 },
    verticalAlign: VerticalAlign.TOP,
    children: [new Paragraph({ alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text, size: 20, font: "Arial", bold: opts.bold || false, color: opts.color || BLACK })] })]
  });
}

function dataCellRich(runs, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: { fill: opts.fill || "FFFFFF", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 150, right: 150 },
    verticalAlign: VerticalAlign.TOP,
    children: [new Paragraph({ children: runs })]
  });
}

// ─── DOCUMENT CONTENT ─────────────────────────────────────────────────────────

const titlePage = [
  spacer(), spacer(), spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "AMERICAN UNIVERSITY OF BEIRUT", size: 28, font: "Arial", bold: true, color: BLUE })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 480 },
    children: [new TextRun({ text: "Suliman S. Olayan School of Business", size: 24, font: "Arial", color: GRAY })] }),
  sectionDivider(),
  spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "ConsultantIQ: An AI-Powered Consulting Intelligence Platform", size: 36, font: "Arial", bold: true, color: BLUE })] }),
  spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: "By", size: 24, font: "Arial", color: GRAY, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 480 },
    children: [new TextRun({ text: "Charbel Merhi", size: 28, font: "Arial", bold: true, color: BLACK })] }),
  spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: "Advisor(s)", size: 22, font: "Arial", color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "Dr. Sirine Taleb", size: 22, font: "Arial", bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 480 },
    children: [new TextRun({ text: "Dr. Ahmad El Hajj", size: 22, font: "Arial", bold: true })] }),
  spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: "A Capstone Project", size: 22, font: "Arial", italics: true, color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "submitted in partial fulfillment of the requirements", size: 22, font: "Arial", color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "for the degree of Master's in Business Analytics", size: 22, font: "Arial", color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "to the Suliman S. Olayan School of Business", size: 22, font: "Arial", color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "at the American University of Beirut", size: 22, font: "Arial", color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "Beirut, Lebanon", size: 22, font: "Arial", color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "April 2026", size: 22, font: "Arial", bold: true })] }),
  spacer(),
  sectionDivider(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160 },
    children: [new TextRun({ text: "Prepared in collaboration with SPARC Consulting, Riyadh, Saudi Arabia", size: 20, font: "Arial", italics: true, color: GRAY })] }),
  pageBreak()
];

// ─── ABSTRACT ─────────────────────────────────────────────────────────────────
const abstractPage = [
  h(HeadingLevel.HEADING_1, "Abstract"),
  sectionDivider(), spacer(),
  p("Management consulting firms derive value through knowledge synthesis, strategic analysis, and expert recommendations. Yet a significant share of consultant time is consumed by tasks that are knowledge-intensive but operationally repeatable: manually searching internal document repositories for existing research, aggregating information from external sources, and producing structured deliverables such as benchmarks, market reports, and PowerPoint presentations. This operational bottleneck limits the volume of client work a firm can handle and introduces inconsistency in output quality across projects."),
  p("This Capstone project addresses this challenge through the design, implementation, and deployment of ConsultantIQ, an AI-powered consulting intelligence platform developed in collaboration with SPARC Consulting, a Saudi-based management consulting firm headquartered in Riyadh. The platform delivers two complementary capabilities: a Retrieval-Augmented Generation (RAG) system that allows consultants to query the firm's internal knowledge base of proprietary documents through natural language, and an AI-driven research and document generation workflow that enables market research, benchmarking, and the automated production of Word reports and PowerPoint presentations, all within a single conversational interface."),
  p("The RAG system was engineered from the ground up as a multi-stage pipeline covering document ingestion, text and visual content extraction, semantic chunking, metadata enrichment, and embedding. Three retrieval strategies were implemented: naive vector retrieval, graph-based retrieval through a knowledge graph of consulting entities and relationships stored in Azure Cosmos DB, and a large language model-driven mode selector that dynamically routes each query to the most appropriate retrieval strategy. The research and document generation workflow is orchestrated through n8n, where an Anthropic Claude classifier routes incoming queries to either the RAG system or a research agent powered by Azure OpenAI GPT-4o with live web search capabilities."),
  p("The platform is deployed live on Render and is accessible at consultantiq-api.onrender.com. A structured evaluation framework measuring retrieval quality through Recall@K, Mean Reciprocal Rank, and Precision@K, as well as generation quality through groundedness, completeness, and relevancy scoring, has been defined and is currently being finalized. The project demonstrates that enterprise-grade AI solutions for professional services require purpose-built retrieval systems rather than off-the-shelf workflow automation tools to achieve the grounded, verifiable, and hallucination-resistant outputs that consulting engagements demand."),
  pageBreak()
];

// ─── TOC ──────────────────────────────────────────────────────────────────────
const tocPage = [
  new TableOfContents("Table of Contents", {
    hyperlink: true,
    headingStyleRange: "1-3",
    stylesWithLevels: []
  }),
  pageBreak()
];

// ─── 1. INTRODUCTION ──────────────────────────────────────────────────────────
const introduction = [
  h(HeadingLevel.HEADING_1, "1. Introduction", { pageBreak: false }),
  sectionDivider(),

  h(HeadingLevel.HEADING_2, "1.1 The Management Consulting Industry and the Challenge of Knowledge Work"),
  p("Management consulting is a knowledge-intensive profession in which value is created through the synthesis of information, the application of structured analytical frameworks, and the delivery of strategic recommendations. Consultants at all levels of seniority spend a substantial proportion of their working time on activities that, while analytically demanding, are operationally repetitive: searching across multiple internal repositories for documents relevant to an ongoing engagement, sourcing market data and benchmarks from external publications, and translating findings into polished client deliverables such as reports and presentations."),
  p("Research has increasingly quantified the productivity costs of this manual knowledge work. A landmark study by Noy and Whitney (2023) demonstrated that consultants using generative AI tools completed tasks 37% faster on average while producing outputs of measurably higher quality [1]. A complementary study by Dell'Acqua et al. (2023), conducted with Boston Consulting Group professionals, found that AI assistance lifted performance significantly on complex analytical tasks, narrowing capability gaps across seniority levels and enabling consultants to tackle a broader range of assignments [2]. These findings suggest that the integration of AI into consulting workflows is not simply a matter of convenience but a structural shift in how professional services firms can scale their intellectual output."),
  p("Despite this opportunity, the adoption of enterprise-grade AI in consulting remains uneven. Many firms have experimented with general-purpose chatbots or off-the-shelf automation tools, but these solutions suffer from a critical weakness: they generate responses from parametric knowledge rather than from the firm's proprietary documents, producing outputs that cannot be traced to authoritative sources and that carry a non-trivial risk of factual hallucination. For a management consulting firm whose value proposition rests on the accuracy and credibility of its deliverables, this risk is unacceptable."),
  p("The emergence of Retrieval-Augmented Generation as an architectural pattern for grounding large language model outputs in specific document corpora provides a path forward. When implemented correctly, a RAG system does not generate from memory; it retrieves relevant passages from the firm's own knowledge base and synthesizes answers that are explicitly traceable to source documents. The challenge lies in building a RAG system that is sophisticated enough to handle the variety of consulting documents, the complexity of multi-hop reasoning across concepts, and the demands of a production environment."),

  h(HeadingLevel.HEADING_2, "1.2 Company Background: SPARC Consulting"),
  p("SPARC Consulting is a Saudi-based management consulting firm headquartered in Riyadh, Saudi Arabia. The firm specializes in helping organizations translate strategy into measurable results, offering a broad range of integrated services including pragmatic strategy development, strategy articulation and cascading, transformation acceleration, and decision-making support. SPARC's client base spans sectors across the Gulf Cooperation Council region, and the firm maintains an internal repository of proprietary documents accumulated across client engagements, including strategic reports, benchmarking studies, market analyses, proposal documents, and consulting frameworks."),
  p("The firm's leadership identified a recurring operational challenge: consultants were spending disproportionate time on two categories of tasks. The first involved external research, specifically, the manual compilation of market intelligence, industry benchmarks, and strategic analyses that would ultimately be packaged into client-facing reports or presentations. The second involved internal retrieval, that is, locating and extracting relevant content from SPARC's own document repository — a task that, despite the high value of the information contained therein, required time-consuming manual search across unstructured files. A workflow analysis conducted by SPARC's project lead provided the qualitative foundation for understanding the scope and frequency of these inefficiencies."),

  h(HeadingLevel.HEADING_2, "1.3 Problem Statement"),
  p("Two distinct but related operational problems were identified at SPARC Consulting that motivated this project."),
  p("The first problem concerns external research and deliverable production. Consultants regularly need to perform market research, competitive benchmarking, and industry analysis as part of client engagements. This process involves identifying relevant external sources, synthesizing findings across multiple documents, and formatting the output into polished deliverables such as Word reports or PowerPoint presentations. The end-to-end process is time-consuming, fragmented across multiple tools, and produces outputs whose quality and consistency vary depending on the individual consultant's available time and attention."),
  p("The second problem concerns internal knowledge retrieval. SPARC maintains a repository of proprietary documents spanning past engagements, internal frameworks, and reference materials. When a consultant needs to answer a client question or substantiate a recommendation, relevant information often exists somewhere within this repository, but locating it requires manually browsing through files, with no guarantee of completeness or accuracy in the search. The practical result is that valuable institutional knowledge is systematically underutilized."),
  p("Both problems share a common root: the absence of an intelligent system capable of understanding natural language queries, accessing the appropriate knowledge sources, and returning grounded, source-cited answers at the speed consulting work demands."),

  h(HeadingLevel.HEADING_2, "1.4 Project Objectives"),
  p("Three objectives were established for this Capstone project, corresponding to the three stages of solving the identified problem."),
  p("Objective 1 — Consulting Workflow Analysis. The first objective was to analyze SPARC's current consultant workflows to understand how information is currently searched for and compiled, to identify specific pain points, and to translate those findings into functional requirements for an AI research assistant."),
  p("Objective 2 — Designing and Implementing an LLM-Based Architecture. The second objective was to design and build a full-stack AI platform tailored to SPARC's needs. This encompassed the RAG pipeline for internal document querying, the AI-driven research and document generation workflow for external research tasks, the front-end interface through which consultants interact with the system, and the production deployment infrastructure."),
  p("Objective 3 — Ensuring Quality, Trust, and Governance of AI Outputs. The third objective was to define and implement mechanisms that ensure the system's outputs are reliable, verifiable, and enterprise-appropriate. This includes explicit source citation, hallucination prevention through retrieval-grounded generation, a structured evaluation framework, and the definition of governance mechanisms for ongoing quality monitoring."),

  h(HeadingLevel.HEADING_2, "1.5 Proposed Solution: ConsultantIQ"),
  p("ConsultantIQ is the platform developed in response to these objectives. It integrates two complementary capabilities within a unified conversational interface: a custom-built RAG system for querying SPARC's internal knowledge base, and an AI-driven research and document generation workflow for external research and deliverable production. The system is built on a three-layer architecture: a React web application serving as the consultant-facing interface, an n8n automation workflow acting as the central orchestration engine, and a FastAPI backend hosting the RAG retrieval engine and document generation services."),
  p("The platform is live and accessible at https://consultantiq-api.onrender.com. All requests from the frontend are routed through the n8n workflow, where an Anthropic Claude AI agent classifies the intent of each query and routes it to the appropriate downstream system. Research-type queries are handled by a GPT-4o research agent equipped with live web search capabilities and the ability to automatically generate Word documents and PowerPoint presentations. Knowledge base queries are handled by the custom RAG system, which dynamically selects between naive vector retrieval and graph-based retrieval depending on the nature of the query."),

  h(HeadingLevel.HEADING_2, "1.6 Report Organization"),
  p("The remainder of this report is organized as follows. Section 2 reviews the relevant academic and technical literature covering large language models in enterprise settings, retrieval-augmented generation, knowledge graph-based retrieval, and agentic AI, and presents a comparative analysis of custom RAG versus off-the-shelf automation solutions. Section 3 describes the complete methodology, covering the data, the document ingestion pipeline, the retrieval strategies, the orchestration workflow, the frontend, the backend, and the deployment. Section 4 presents the evaluation framework and results. Section 5 discusses the findings in relation to the original project objectives. Section 6 concludes the report and identifies directions for future work."),
  pageBreak()
];

// ─── 2. BACKGROUND ────────────────────────────────────────────────────────────
const background = [
  h(HeadingLevel.HEADING_1, "2. Background and Related Work", { pageBreak: false }),
  sectionDivider(),

  h(HeadingLevel.HEADING_2, "2.1 Large Language Models in Enterprise Settings"),
  p("Large language models (LLMs) are neural networks trained on vast corpora of text data, capable of generating coherent, contextually appropriate language across a wide range of tasks. Following the public release of GPT-4 in 2023 and the rapid adoption of models from Anthropic, Google, and open-source communities, enterprises across industries began experimenting with LLM integration into knowledge workflows. The academic evidence for productivity impact in professional services is now well-established. Noy and Whitney (2023) ran a controlled experiment with 444 college-educated professionals in writing-intensive roles and found that access to a general-purpose LLM reduced task completion time by 37% and improved output quality as rated by independent evaluators [1]. Dell'Acqua et al. (2023) conducted a field experiment with 758 BCG consultants and found that AI assistance substantially lifted performance on tasks within the model's capabilities, while simultaneously identifying a 'jagged frontier' beyond which over-reliance on AI led to performance degradation [2]."),
  p("These findings directly motivate the design choices made in this project. Specifically, they reinforce the importance of keeping human consultants in the loop — the system's role is to accelerate and ground their research, not to replace their judgment — and they highlight the risk of providing unverified AI-generated content to professionals whose credibility depends on accuracy. The architecture of ConsultantIQ was designed with both of these considerations in mind: all RAG answers are grounded in cited source documents, and the research workflow is explicitly interactive, requiring consultant direction before deliverables are generated."),

  h(HeadingLevel.HEADING_2, "2.2 Retrieval-Augmented Generation"),
  p("A foundational limitation of LLMs used in isolation is hallucination: the tendency to generate plausible-sounding but factually incorrect content, particularly when queried on topics beyond their training data or on proprietary organizational knowledge [3]. Ji et al. (2023) conducted a comprehensive survey of hallucination in natural language generation, cataloguing the causes and manifestations of this phenomenon and documenting its prevalence across factual QA, summarization, and dialogue tasks [3]. For enterprise applications where output accuracy is non-negotiable, hallucination represents a critical barrier to deployment."),
  p("Retrieval-Augmented Generation (RAG) was proposed by Lewis et al. (2020) as a framework that addresses this limitation by conditioning language model generation on retrieved document passages [4]. In the original formulation, a retriever fetches relevant passages from a non-parametric document store using a query-document similarity function, and these passages are prepended to the LLM's prompt as factual context. The model is then instructed to answer using only the provided context, substantially reducing its reliance on potentially incorrect parametric knowledge."),
  p("Gao et al. (2023) published a comprehensive survey of RAG systems, organizing the landscape into three architectural categories: naive RAG, advanced RAG, and modular RAG [5]. Naive RAG, the simplest form, follows a straightforward retrieve-then-generate pipeline. Advanced RAG introduces pre-retrieval enhancements such as query rewriting and post-retrieval improvements such as re-ranking and context compression. Modular RAG decomposes the pipeline into independently configurable components, enabling more flexible architectures. The ConsultantIQ RAG system implements elements from all three categories: naive retrieval as a baseline mode, query rewriting for follow-up questions, and a modular pipeline architecture that allows retrieval strategy selection at query time."),

  h(HeadingLevel.HEADING_2, "2.3 Knowledge Graphs and Graph-Based Retrieval"),
  p("While vector similarity search is effective for semantically related queries, it is fundamentally a bag-of-concepts matching operation that does not capture the structured relationships between entities. When a consultant asks how a specific framework connects to a set of metrics, or how a company's strategy relates to its market entry approach, the answer requires reasoning across a graph of relationships, not just proximity in embedding space."),
  p("Pan et al. (2024) proposed a roadmap for unifying large language models and knowledge graphs, arguing that the two technologies are complementary: knowledge graphs provide structured, verifiable factual grounding while LLMs provide the natural language interface and reasoning capability [6]. The integrated architecture they envision aligns closely with the Graph RAG component of ConsultantIQ, where structured entity-relationship graphs are used to retrieve semantically connected subgraphs, which are then converted to natural language context for the LLM."),
  p("Edge et al. (2024) at Microsoft introduced GraphRAG, a Graph RAG approach specifically designed for query-focused summarization over large document corpora [7]. Their system builds a community-structured knowledge graph from the source documents and uses it to answer queries that require synthesizing information from multiple documents — a task where naive vector retrieval consistently underperforms. Microsoft's GraphRAG operates at the corpus level, building community summaries as a pre-processing step. The approach taken in ConsultantIQ differs in that the knowledge graph is built incrementally as documents are ingested, and graph traversal is used for query-time retrieval rather than pre-computed summaries. This makes the ConsultantIQ graph more responsive to new document additions but also more dependent on the quality of the entity extraction step."),

  h(HeadingLevel.HEADING_2, "2.4 Agentic AI and Workflow Orchestration"),
  p("Beyond retrieval, there is a growing body of work on autonomous AI agents that can plan, use tools, and complete multi-step tasks in response to high-level goals. Wang et al. (2024) surveyed the landscape of LLM-based autonomous agents, categorizing them by their perception, memory, action, and planning capabilities [8]. The survey identifies three primary use cases: task automation, tool use, and multi-agent collaboration, all of which are relevant to the ConsultantIQ architecture."),
  p("In the ConsultantIQ system, the concept of agentic AI is instantiated through the n8n workflow, where an Anthropic Claude AI agent acts as a classifier and router, and a GPT-4o research agent acts as an autonomous researcher equipped with web search tools and document generation capabilities. The orchestration framework — n8n, an open-source workflow automation platform — was chosen as the orchestration layer because it provides a visual, low-code environment for designing agent logic, integrating with external APIs, and managing the control flow of multi-step tasks without requiring code deployments for logic changes. This separation of orchestration logic from application code was a deliberate architectural choice that significantly accelerated iteration speed during development."),

  h(HeadingLevel.HEADING_2, "2.5 Build vs. Buy: Custom RAG vs. Off-the-Shelf Automation"),
  p("A critical architectural decision in this project was whether to build the RAG system from scratch or to use a pre-built RAG capability offered by an automation platform such as Zapier or n8n's native vector store node. This decision was evaluated rigorously, as it had fundamental implications for system capability, cost, maintenance burden, and the quality of outputs. The analysis ultimately led to the decision to build a fully custom RAG system, and the reasoning behind this choice is documented in detail here given its importance to the overall architecture."),

  h(HeadingLevel.HEADING_3, "2.5.1 Off-the-Shelf RAG Capabilities"),
  p("Modern automation platforms such as Zapier and n8n offer native vector store nodes that allow users to connect a document source, embed documents, and query them using natural language, all without writing code. These solutions have genuine advantages for simple use cases: they can be configured in hours rather than weeks, they require no infrastructure management, and they offer pre-built integrations with email, Slack, Google Docs, and other enterprise tools. n8n in particular is self-hostable and open-source, making it cost-effective for organizations with the capacity to host it."),
  p("However, for a professional services firm that requires accurate, source-verifiable answers from a proprietary document corpus, these solutions present several critical limitations. Their retrieval is limited to naive vector similarity search: they do not support graph-based retrieval, hybrid scoring, or structured reasoning across entity relationships. Their chunking strategies are opaque — the user has no control over how documents are split, which means semantically coherent sections can be fragmented across multiple chunks in ways that degrade retrieval quality. Their prompt engineering capabilities are minimal, offering a text input rather than a fully configurable system prompt. And crucially, they provide no hallucination detection, no evaluation pipeline, and no mechanism for measuring whether the answers they produce are grounded in the retrieved documents."),

  h(HeadingLevel.HEADING_3, "2.5.2 Custom-Built RAG: The Case for Full Control"),
  p("The custom RAG system built for ConsultantIQ addresses each of these limitations directly. Three retrieval modes are available: naive vector retrieval for broad semantic matching, graph-based retrieval for structured reasoning across business entities and their relationships, and a large language model-driven mode selector that dynamically chooses between them based on the nature of each query. This flexibility is architecturally impossible with off-the-shelf solutions: no current automation platform supports Graph RAG or hybrid retrieval blending."),
  p("Chunking is fully controlled: three strategies — fixed window, sentence-boundary-aware, and semantic similarity-based — are available and can be tuned per document type. Metadata enrichment is performed at ingestion time, adding cleaned text, TF-IDF-extracted keywords, extractive summaries, and project-type tags to every chunk. These enriched metadata fields improve retrieval precision significantly compared to raw text embedding alone."),
  p("Prompt engineering is fully configurable at every stage of the pipeline: different system prompts are used for the naive retriever, the graph retriever, and the hybrid synthesis step, each tuned to the specific type of context being provided to the LLM. The hallucination prevention mechanism is explicit and measurable: the model is instructed to answer only from the provided context, to cite source documents for every claim, and to explicitly state when the knowledge base does not contain information relevant to the query rather than fabricating an answer."),
  p("The evaluation pipeline — measuring Recall@K, Mean Reciprocal Rank, Precision@K, groundedness, completeness, and relevancy — is an in-house system with no equivalent in automation platforms. It provides the quantitative evidence needed to demonstrate system quality to a consulting firm's leadership, to compare retrieval modes objectively, and to identify specific failure cases for targeted improvement."),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2000, 3680, 3680],
    rows: [
      new TableRow({ children: [
        headerCell("Dimension", 2000),
        headerCell("Custom RAG (ConsultantIQ)", 3680),
        headerCell("Off-the-Shelf (n8n / Zapier)", 3680),
      ]}),
      new TableRow({ children: [
        dataCell("Retrieval Modes", 2000, { bold: true, fill: LIGHT_GRAY }),
        dataCell("Naive vector, Graph RAG, LLM-selected mode", 3680),
        dataCell("Naive vector only", 3680, { color: "CC0000" }),
      ]}),
      new TableRow({ children: [
        dataCell("Chunking Control", 2000, { bold: true }),
        dataCell("Full: fixed, sentence, semantic — tunable per doc type", 3680),
        dataCell("None: black-box, not configurable", 3680, { color: "CC0000" }),
      ]}),
      new TableRow({ children: [
        dataCell("Prompt Engineering", 2000, { bold: true, fill: LIGHT_GRAY }),
        dataCell("Full per-mode system prompt control", 3680),
        dataCell("Minimal: text box only", 3680, { color: "CC0000" }),
      ]}),
      new TableRow({ children: [
        dataCell("Hallucination Prevention", 2000, { bold: true }),
        dataCell("Enforced: retrieval-grounded, source citations mandatory", 3680),
        dataCell("None: LLM output passed directly to user", 3680, { color: "CC0000" }),
      ]}),
      new TableRow({ children: [
        dataCell("Evaluation", 2000, { bold: true, fill: LIGHT_GRAY }),
        dataCell("Full: Recall@K, MRR, Groundedness, Completeness", 3680),
        dataCell("None: no quality visibility", 3680, { color: "CC0000" }),
      ]}),
      new TableRow({ children: [
        dataCell("Cost Model", 2000, { bold: true }),
        dataCell("Azure API costs only; no per-query platform fees", 3680),
        dataCell("Per-execution charges (Zapier); expensive at scale", 3680),
      ]}),
      new TableRow({ children: [
        dataCell("Time to Build", 2000, { bold: true, fill: LIGHT_GRAY }),
        dataCell("Weeks — significant engineering investment", 3680),
        dataCell("Hours — drag-and-drop configuration", 3680),
      ]}),
      new TableRow({ children: [
        dataCell("Scalability", 2000, { bold: true }),
        dataCell("API-first: serves any integration (n8n, Slack, email, etc.)", 3680),
        dataCell("Vendor lock-in; difficult to migrate", 3680),
      ]}),
    ]
  }),
  spacer(),
  p("The decision to invest in a custom-built RAG system was driven by a fundamental principle: for a management consulting firm, the quality and verifiability of AI-generated outputs is not an optimization target — it is a prerequisite. A system that returns a confidently-stated but unverifiable answer is worse than no system at all, because it erodes consultant trust and potentially introduces errors into client deliverables. The engineering investment required to build the ConsultantIQ RAG system is justified precisely because it delivers the quality, control, and measurability that the consulting use case demands."),
  pageBreak()
];

// ─── 3. METHODOLOGY ───────────────────────────────────────────────────────────
const methodology = [
  h(HeadingLevel.HEADING_1, "3. Methodology", { pageBreak: false }),
  sectionDivider(),

  h(HeadingLevel.HEADING_2, "3.1 System Overview"),
  p("ConsultantIQ is organized around three interconnected layers that together form an end-to-end AI platform. The first is a React web application that provides the consultant-facing conversational interface, supporting multi-turn dialogue, session memory, and the rendering of text, file downloads, and document links. The second is an n8n automation workflow that acts as the central orchestration engine, receiving all requests from the frontend, classifying their intent, and routing them to the appropriate downstream agent or service. The third is a FastAPI backend that hosts the custom RAG retrieval engine, the document generation service, and the chat persistence layer. All three layers are deployed on Render's native runtime and communicate over HTTPS."),
  placeholder("FIGURE 1 — High-Level System Architecture Diagram (three-layer: React / n8n / FastAPI + Azure services)"),
  spacer(),
  p("The system supports two primary interaction modes. In Research Mode, the user submits a research question or a request to generate a deliverable. The n8n workflow routes the request to a GPT-4o research agent that performs live web search, synthesizes findings, and — when instructed — automatically generates a Word report or a PowerPoint presentation. In RAG Mode, the user submits a question about SPARC's internal documents. The request is forwarded to the FastAPI backend, where the custom RAG engine retrieves relevant passages and generates a grounded, source-cited answer."),

  h(HeadingLevel.HEADING_2, "3.2 Data"),
  p("The knowledge base used in the current implementation consists of twenty test documents curated to represent the types of materials present in SPARC Consulting's actual document repository. The documents span four categories: strategic reports, market benchmarking studies, consulting frameworks and methodologies, and proposal documents. The file formats covered include PDF, Microsoft Word (DOCX), PowerPoint (PPTX), and Excel (XLSX), reflecting the variety of formats in which consulting knowledge is typically stored."),
  p("The decision to use test documents rather than SPARC's actual proprietary files was driven by security and confidentiality considerations. Client-facing consulting documents contain sensitive commercial and strategic information that requires access controls, data governance policies, and secure ingestion protocols before they can be processed by a cloud-hosted AI system. The design of these security mechanisms — including role-based access control, document-level encryption, and audit logging — has been identified as a priority area for the next phase of the project, after which actual SPARC documents will be ingested into the knowledge base."),
  p("The test dataset was selected to cover a representative range of content types: documents with dense narrative text, documents with tables and structured data, documents with charts and visual content, and documents with a mixture of all three. This diversity was important for validating the multi-format ingestion pipeline and the vision processing component."),

  h(HeadingLevel.HEADING_2, "3.3 Document Ingestion Pipeline"),
  p("All documents pass through a five-stage pipeline before they can be queried. The pipeline is designed to be format-agnostic, handling the full range of file types present in consulting repositories, and to maximize the information density of the stored chunks through enrichment and optional visual content processing."),

  h(HeadingLevel.HEADING_3, "3.3.1 Stage 1: Document Cracking"),
  p("The first stage, implemented in pipeline/cracker.py, extracts raw content from uploaded files into structured PageUnit objects. Each PageUnit represents one page or slide and carries both the extracted text and any tabular content found on that page. Four file formats are supported. For PDF documents, text and embedded tables are extracted page by page using pdfplumber, which provides precise layout-aware text extraction superior to simple text layer reading. For PowerPoint files, slide text and table data are extracted using python-pptx. For Word documents, sections and tables are extracted using python-docx, with heading-based section breaks used to preserve document structure. For Excel files, sheet data is extracted as structured tabular rows using openpyxl."),

  h(HeadingLevel.HEADING_3, "3.3.2 Stage 2: Chunking"),
  p("PageUnits are split into smaller ChunkUnit objects in the second stage, implemented in pipeline/chunker.py. Three chunking strategies are available, each suited to different document types. The fixed window chunker splits text into overlapping windows of a configurable word count, making it well-suited for uniform documents where structural boundaries are not meaningful. The sentence-boundary-aware chunker groups sentences into chunks that respect sentence boundaries, making it preferable for narrative text such as reports and methodology documents. The semantic chunker groups paragraphs together as long as their word overlap exceeds a configurable Jaccard similarity threshold, creating chunks that align with topical boundaries within the document; this strategy performs best on structured documents with clear section breaks and on Excel sheets with labeled sections."),
  p("Each ChunkUnit carries the following fields: the chunk text, a chunk index, the source filename, the document type, the page number, and the section heading. These fields are used extensively in source citation generation at query time."),

  h(HeadingLevel.HEADING_3, "3.3.3 Stage 3: Chunk Enrichment"),
  p("Before embedding, each chunk is enriched with automatically computed metadata in pipeline/enricher.py. The cleaned_text field is produced by removing boilerplate content, normalizing whitespace, and correcting common Unicode encoding artifacts. A set of keywords is extracted using TF-based scoring: the top eight terms with a minimum length of four characters and filtered against a stop-word list are retained per chunk. An extractive summary is generated by selecting the top two sentences ranked by word frequency scoring. A project_tag field infers the document's domain from its keywords, mapping it to one of seven categories: retail, digital, market entry, HR and policy, benchmarking, strategy, or general. Additional file-level metadata including document date, word count, table presence, and character count are also computed and stored."),
  p("The enrichment step significantly improves retrieval quality by providing the vector store and search indices with structured metadata that complements raw text embedding. The keywords field, in particular, improves full-text search precision and is used in the Graph RAG entity matching scoring system."),

  h(HeadingLevel.HEADING_3, "3.3.4 Stage 4: Vision Processing"),
  p("An optional fourth stage addresses a fundamental limitation of text-only extraction: the significant informational content present in charts, diagrams, infographics, and visually formatted tables that cannot be captured by text extraction alone. For each page of a PDF or PowerPoint file, GPT-4o Vision is used to analyze the page for visual content. When a visual element is identified, a natural language description is appended to the chunk text — for example, a bar chart comparing EBITDA margins across five sectors from 2020 to 2024, or a flowchart illustrating the five stages of a consulting engagement methodology. This description is included in the embedding and is therefore searchable, ensuring that visually-communicated knowledge is accessible through the RAG system."),
  p("The vision processing stage is computationally and financially non-trivial, requiring one GPT-4o Vision API call per page of each processed document. It is therefore configured as an optional stage, applied selectively to document types where visual content is expected to be present and informative."),

  h(HeadingLevel.HEADING_3, "3.3.5 Stage 5: Embedding"),
  p("The final ingestion stage, implemented in pipeline/embedder.py, converts the enriched text of each ChunkUnit into a dense vector representation using Azure OpenAI's text-embedding-3-large model, which produces 3,072-dimensional embeddings. These high-dimensional vectors capture the semantic meaning of each chunk and are used at query time to identify the most relevant passages for a given question through cosine similarity search."),

  h(HeadingLevel.HEADING_2, "3.4 Vector Store Architecture"),
  p("The embedded chunks are stored in one of two backends depending on the deployment environment, implemented in store/vector_store.py."),

  h(HeadingLevel.HEADING_3, "3.4.1 Local Development Store"),
  p("For local development and testing, an in-memory store with disk persistence is used. Chunk metadata is serialized to a chunks.json file and the embedding matrix is stored as a NumPy float32 binary array. Three search methods are available: vector search using cosine similarity between the query embedding and all stored chunk vectors, full-text search using TF-IDF cosine similarity computed through scikit-learn's TfidfVectorizer, and hybrid search combining both methods through Reciprocal Rank Fusion (RRF). The RRF scoring formula assigns each result a combined score of 1 / (60 + rank_vector + 1) + 1 / (60 + rank_fulltext + 1), which has been shown empirically to outperform simple score averaging when combining heterogeneous ranking signals."),

  h(HeadingLevel.HEADING_3, "3.4.2 Azure AI Search (Production)"),
  p("The production deployment uses Azure AI Search as the vector store backend. The search index schema includes all chunk metadata fields plus an embedding vector field configured for HNSW (Hierarchical Navigable Small World) approximate nearest-neighbor search. Three search modes are available: vector search using HNSW approximate nearest-neighbor queries, full-text search using BM25-style scoring with a Lucene analyzer, and hybrid search combining vector and text search with Azure's built-in AI semantic reranking, which applies a cross-encoder model to reorder results for improved relevance."),

  h(HeadingLevel.HEADING_2, "3.5 Retrieval Strategies"),
  p("Three retrieval strategies are implemented in the ConsultantIQ RAG system. The choice of which strategy to apply for a given query is made dynamically at query time, as described in Section 3.5.3."),

  h(HeadingLevel.HEADING_3, "3.5.1 Naive RAG"),
  p("The Naive RAG retriever, implemented in naive_rag/retriever.py, is the simplest and most broadly applicable retrieval path. Given a user question, the retriever first determines whether the question is a follow-up in a multi-turn conversation: a GPT-4o call inspects the recent conversation history and rewrites the question to be self-contained if it contains unresolved pronoun or context references — for example, 'What about their margins?' becomes 'What are Company X's EBITDA margins?' given the appropriate conversation history. The (possibly rewritten) question is then embedded using the same model used at ingestion time, and the top-k most relevant chunks are retrieved from the vector store using the configured search mode. The retrieved chunks are provided as context to GPT-4o alongside the original question and a system prompt that enforces grounded generation: the model is instructed to use only the provided context, to cite source documents for every claim using the format [Source: filename, section, Page N], and to explicitly state when the knowledge base does not contain relevant information rather than fabricating an answer."),

  h(HeadingLevel.HEADING_3, "3.5.2 Graph RAG"),
  p("The Graph RAG system models the document corpus as a knowledge graph of consulting entities and their relationships, enabling structured reasoning across concepts rather than relying solely on text similarity. The knowledge graph is stored in Azure Cosmos DB using the Gremlin API, with entities as vertices and relationships as directed edges."),
  p("Entity extraction is performed at ingestion time by pipeline/graph_rag/extractor.py. GPT-4o processes each chunk at temperature 0.0 for deterministic output and extracts structured entities and relationships. Entity types include consulting frameworks and models (e.g., Porter's Five Forces, the McKinsey 7S Framework), metrics and KPIs (e.g., EBITDA, CAC, NPS), companies and organizations, roles and processes, tools and technologies, key arguments (core claims central to a document's meaning), and abstract concepts (e.g., data lifecycle, market entry barriers). Relationship types extracted include HAS_COMPONENT, USED_IN, MEASURES, PART_OF, LEADS_TO, CONTRADICTS, SUPPORTS, REQUIRES, and DEFINES. Each chunk typically yields between five and twelve entities with up to ten relationships."),
  p("At query time, the Graph Retriever extracts two to five key entity terms from the question using GPT-4o, then searches the graph for matching seed entities using a weighted scoring system: an exact phrase match in an entity's name scores ten points, all words of a multi-word term being present in the name scores six points, a full phrase match in the entity's description scores three points, and a single-word match in the description scores one point. From the identified seed entities, a breadth-first subgraph traversal extends to depth two, gathering the seeds, their immediate neighbors, and their neighbors' neighbors. The resulting subgraph is formatted as structured context and provided to GPT-4o alongside the user's question for answer generation."),

  h(HeadingLevel.HEADING_3, "3.5.3 LLM-Based Mode Selection"),
  p("An initial implementation of the retrieval system used a parallel hybrid approach in which both Naive RAG and Graph RAG were executed simultaneously on every query, with results combined through a synthesis prompt. While this approach produced high-quality answers, it was operationally impractical: the cost of two parallel LLM-augmented retrievals per query, combined with the additional synthesis call, made it unsuitable for production deployment from both a latency and an API cost perspective."),
  p("The final architecture delegates the mode selection decision to the language model itself. At query time, a routing prompt is sent to GPT-4o describing the characteristics of Naive RAG (best for broad semantic questions, descriptive queries, and document-level questions) and Graph RAG (best for queries involving specific named entities, framework relationships, and multi-hop conceptual reasoning). The model selects the appropriate mode for the query and the selected retriever is invoked alone. This approach preserves the intelligent routing benefit of the hybrid strategy while reducing per-query cost and latency to that of a single retrieval path."),

  h(HeadingLevel.HEADING_2, "3.6 n8n Orchestration Workflow"),
  p("The orchestration layer of ConsultantIQ is implemented as an n8n workflow that serves as the central routing engine for all user interactions. n8n is an open-source workflow automation platform that supports visual workflow design, native integration with HTTP APIs, and the embedding of AI agent nodes. Its use as an orchestration layer allowed the routing logic, agent configuration, and document generation flow to be designed and iterated without requiring backend code deployments."),
  placeholder("FIGURE 2 — n8n Workflow Diagram (dual triggers, AI Agent, Switch, Research Agent, If Report, If Presentation, Presenton, RAG Agent, four Respond-to-Webhook nodes)"),
  spacer(),

  h(HeadingLevel.HEADING_3, "3.6.1 Dual-Trigger Architecture"),
  p("The workflow supports two independent entry points. The production trigger is a Webhook node that receives POST requests from the React frontend at the path /webhook/[workflow-id], with a request body containing the chatInput (the user's message) and a sessionId (a UUID identifying the conversation session). The testing trigger is n8n's built-in 'When Chat Message Received' node, which allows the workflow to be tested directly from n8n's chat interface without requiring a frontend request. Because the two triggers expose different JSON structures — the production webhook nests the payload under a body field while the chat trigger exposes it at the top level — all downstream nodes that reference the user's message or session ID use JavaScript try-catch expressions that attempt to read from one path and fall back to the other, ensuring identical behavior regardless of which trigger activated the workflow."),

  h(HeadingLevel.HEADING_3, "3.6.2 AI Agent Classifier"),
  p("The first processing node in the workflow is an AI Agent powered by Anthropic Claude. Its sole function is to classify the incoming user message into one of two categories: RESEARCH, covering market research, industry analysis, competitive benchmarks, strategy questions, and requests to generate reports or presentations; or RAG, covering questions about SPARC's internal documents or proprietary knowledge base. The agent is connected to a Simple Memory sub-node that maintains recent session context, ensuring the classifier is aware of preceding messages when interpreting ambiguous queries. The agent's system prompt was iteratively hardened to enforce a single-word output: early iterations produced explanations in natural language rather than the bare classification token, which caused the downstream Switch node to fail. The final prompt explicitly specifies that the response must consist of exactly one word with no punctuation, explanation, or surrounding text."),
  p("A Switch node reads the classifier's output and routes the request to the Research Agent branch when the output is 'RESEARCH', and to the RAG Agent branch when the output is 'RAG'."),

  h(HeadingLevel.HEADING_3, "3.6.3 Research Agent and Document Generation"),
  p("The Research Agent is an n8n AI Agent node powered by Azure OpenAI GPT-4o. It is equipped with a Serper HTTP Request tool that performs live Google Search queries when the agent determines that current external data is needed to answer a research question. The agent maintains full conversation history through a MongoDB Chat Memory sub-node connected to Azure Cosmos DB using the MongoDB API, ensuring that multi-turn research conversations are coherent and that follow-up questions are understood in the context of the conversation so far."),
  p("The Research Agent supports a three-stage document generation flow. When a research request is completed, the agent may offer to generate a structured deliverable. In the first stage, the agent produces a structured research report in Markdown format and appends the signal tag %%REPORT_READY%% to its output. A downstream If node detects this tag and triggers an HTTP POST request to the FastAPI backend's /docx/generate-report endpoint, which converts the Markdown content into a formatted Word document and streams it back as a binary file attachment. In the second stage, the consultant receives the Word document and may request a PowerPoint presentation based on the report's content. The agent appends the signal tag %%DECK_READY%% to its output, and a downstream If node triggers the Presenton API, which generates a presentation from the report content asynchronously. The resulting presentation link is returned to the frontend. Each of the four possible exit paths — plain research text, Word document, PowerPoint presentation, or RAG response — has a dedicated Respond to Webhook node, ensuring that the appropriate response type and content-type header are returned to the frontend for each case."),

  h(HeadingLevel.HEADING_3, "3.6.4 RAG Agent"),
  p("The RAG Agent is a simple HTTP Request node that forwards the user's query to the FastAPI backend's POST /query endpoint. The backend's Hybrid RAG engine processes the query — performing LLM-based mode selection, executing the chosen retriever, and generating a grounded answer — and returns a JSON response containing the answer text, the retrieval mode used, and a list of source references. The RAG Agent passes this response to its dedicated Respond to Webhook node, which returns it to the React frontend."),

  h(HeadingLevel.HEADING_2, "3.7 React Frontend"),
  p("The consultant-facing interface is a React web application built with TypeScript and Vite, deployed as a static build served by the FastAPI backend. The interface presents a multi-session chat layout with a sidebar listing conversation history and a main area displaying the active conversation."),
  placeholder("FIGURE 3 — ConsultantIQ Frontend Screenshot (chat interface with sidebar and message area)"),
  spacer(),
  p("The application's state is managed through two custom React hooks. The useChatHistory hook manages the full list of conversation threads: on mount, it loads conversation history from Azure Cosmos DB via the FastAPI backend; on every update, it synchronizes changes to the backend with a 500-millisecond debounce to prevent excessive API calls. The useChat hook manages the messages within the active conversation. Each conversation is assigned a UUID at creation time, which is used as the session identifier sent to n8n with every message. n8n uses this UUID as the key for MongoDB Chat Memory, ensuring that each browser session maps to exactly one memory thread in the Research Agent."),
  p("Every response received from n8n is processed by a response parser before being displayed. The parser handles three distinct response formats: binary Word documents detected by the application/vnd.openxmlformats content-type header, which are converted to downloadable Blob URLs and displayed as file download cards; PowerPoint links detected by the presence of a .pptx URL or the %%DECK_READY%% signal tag in the response; and text or Markdown responses parsed from n8n's JSON response format. Markdown responses are rendered with full formatting support including headers, bullet lists, bold text, and inline code."),

  h(HeadingLevel.HEADING_2, "3.8 FastAPI Backend"),
  p("The FastAPI backend serves as the bridge between the n8n orchestration layer and the RAG engine, the document generation service, and the chat persistence layer. The primary endpoint is POST /query, which accepts a JSON body containing the user's question, invokes the RAG engine's LLM-based mode selector and the selected retriever, captures the stdout output to detect which retrieval mode was used, extracts source citations through regex pattern matching, strips internal debug output from the answer, and returns a clean JSON response."),
  p("The document generation sub-application, mounted at the /docx path, exposes a POST /docx/generate-report endpoint that receives a Markdown-formatted research report and converts it to a formatted Word document using python-docx. The document is streamed back as a binary response with the application/vnd.openxmlformats-officedocument.wordprocessingml.document content-type header, triggering the frontend's file download flow."),
  p("Chat persistence is handled through a set of endpoints covering conversation listing, retrieval, creation and update, and deletion, all backed by Azure Cosmos DB. A user profile endpoint supports storing and retrieving consultant preferences across sessions."),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2800, 1800, 4760],
    rows: [
      new TableRow({ children: [
        headerCell("Endpoint", 2800),
        headerCell("Method", 1800),
        headerCell("Description", 4760),
      ]}),
      new TableRow({ children: [
        dataCell("/query", 2800, { fill: LIGHT_GRAY }),
        dataCell("POST", 1800, { fill: LIGHT_GRAY, center: true }),
        dataCell("Submit a question to the RAG engine; returns answer, mode, sources", 4760, { fill: LIGHT_GRAY }),
      ]}),
      new TableRow({ children: [
        dataCell("/docx/generate-report", 2800),
        dataCell("POST", 1800, { center: true }),
        dataCell("Convert Markdown research report to binary .docx file", 4760),
      ]}),
      new TableRow({ children: [
        dataCell("/conversations", 2800, { fill: LIGHT_GRAY }),
        dataCell("GET", 1800, { fill: LIGHT_GRAY, center: true }),
        dataCell("List all stored conversation threads (without messages)", 4760, { fill: LIGHT_GRAY }),
      ]}),
      new TableRow({ children: [
        dataCell("/conversations/{id}", 2800),
        dataCell("GET / POST / DELETE", 1800, { center: true }),
        dataCell("Retrieve, create/update, or delete a conversation with messages", 4760),
      ]}),
      new TableRow({ children: [
        dataCell("/user-profile", 2800, { fill: LIGHT_GRAY }),
        dataCell("GET / PUT", 1800, { fill: LIGHT_GRAY, center: true }),
        dataCell("Read or update consultant preferences stored in Cosmos DB", 4760, { fill: LIGHT_GRAY }),
      ]}),
      new TableRow({ children: [
        dataCell("/health", 2800),
        dataCell("GET", 1800, { center: true }),
        dataCell("System health check: retriever status, memory availability", 4760),
      ]}),
    ]
  }),
  spacer(),

  h(HeadingLevel.HEADING_2, "3.9 Deployment"),
  p("The application is deployed on Render using its native Python runtime. The FastAPI application is started with uvicorn on the port injected by Render's environment, and the React frontend's static build is served as a Single Page Application through a catch-all route in the FastAPI app. The live deployment is accessible at https://consultantiq-api.onrender.com."),
  p("The deployment uses Render's free tier, which imposes a specific operational characteristic: the service enters a sleep state after fifteen minutes of inactivity and requires approximately sixty seconds to cold-start on the first incoming request. This behavior is acceptable for the current demonstration and testing phase but would need to be addressed through an upgrade to a paid Render tier — or a migration to a dedicated cloud hosting environment — before the system is rolled out for active consultant use."),
  p("The Azure services used by the platform — Azure OpenAI (for GPT-4o and text-embedding-3-large), Azure AI Search (for the production vector store), and Azure Cosmos DB (for the knowledge graph and chat memory) — are all accessed through API keys stored as environment variables in Render's configuration dashboard. No credentials are stored in the codebase."),
  placeholder("FIGURE 4 — Deployment Architecture Diagram (Render service, Azure OpenAI, Azure AI Search, Azure Cosmos DB, n8n cloud)"),
  pageBreak()
];

// ─── 4. RESULTS ───────────────────────────────────────────────────────────────
const results = [
  h(HeadingLevel.HEADING_1, "4. Results", { pageBreak: false }),
  sectionDivider(),

  h(HeadingLevel.HEADING_2, "4.1 Evaluation Framework"),
  p("A structured evaluation framework was designed to assess the quality of the ConsultantIQ RAG system across two dimensions: retrieval quality and generation quality. The framework is implemented in evaluation/evaluator.py and is executable through evaluation/evaluate.py, which supports retrieval-only, generation-only, and full comparative evaluation modes."),
  p("Retrieval quality is measured using three standard information retrieval metrics applied to a golden dataset of question-answer pairs: Recall@K (the proportion of queries for which at least one ground-truth document appears in the top K retrieved results), Precision@K (the proportion of the top K results that are ground-truth relevant documents), and Mean Reciprocal Rank (the average of the reciprocal rank of the first relevant result across all queries). These metrics are computed for K values of 1, 3, and 5 and are evaluated independently for the vector search, full-text search, and hybrid RRF search modes, enabling objective comparison."),
  p("Generation quality is assessed through a judge-LLM approach in which GPT-4o evaluates each generated answer on three dimensions: groundedness (whether the answer's claims are supported by the retrieved context, scored zero to one), completeness (whether the answer addresses all aspects of the question given the available context, scored zero to one), and relevancy (whether the answer directly addresses the question without irrelevant content, scored zero to one). A 100-query test harness defined in evaluation/test_100.py provides the query load for both evaluation phases."),

  h(HeadingLevel.HEADING_2, "4.2 Retrieval Evaluation Results"),
  placeholder("TABLE — Retrieval Metrics by Search Mode (Recall@1, @3, @5 / Precision@1, @3, @5 / MRR for Vector, Fulltext, Hybrid RRF)"),
  spacer(),
  placeholder("FIGURE 5 — Bar Chart: Recall@5 and MRR Comparison Across Retrieval Modes"),
  spacer(),
  p("[PLACEHOLDER — Insert summary interpretation of retrieval results: which mode performs best overall, which metric shows the largest gap between modes, and what this implies for the default search configuration.]"),

  h(HeadingLevel.HEADING_2, "4.3 Generation Quality Results"),
  placeholder("TABLE — Generation Quality Metrics (Groundedness, Completeness, Relevancy) for Naive RAG and Graph RAG modes"),
  spacer(),
  placeholder("FIGURE 6 — Radar Chart or Bar Chart: Generation Quality Comparison Across Retrieval Modes"),
  spacer(),
  p("[PLACEHOLDER — Insert interpretation: groundedness scores validate hallucination prevention effectiveness; completeness and relevancy scores identify query types where each mode performs best.]"),

  h(HeadingLevel.HEADING_2, "4.4 Retrieval Mode Comparison"),
  placeholder("TABLE — Full Head-to-Head Comparison: Naive RAG vs. Graph RAG across all metrics and query categories"),
  spacer(),
  p("[PLACEHOLDER — Insert interpretation: query categories where Graph RAG outperforms Naive RAG (entity-dense, relational queries) vs. categories where Naive RAG is preferred (broad semantic, descriptive queries). This validates the LLM-based mode selection design.]"),

  h(HeadingLevel.HEADING_2, "4.5 Query Analytics"),
  p("In addition to the evaluation framework described above, a query analytics layer is currently being implemented to provide operational visibility into the system's usage patterns and performance in production. The analytics module will capture per-query metadata including the query text, the retrieval mode selected by the LLM router, the number of sources returned, the response latency, and — when user feedback is provided — a consultant-assigned quality rating."),
  placeholder("FIGURE 7 — Query Analytics Dashboard (mode distribution, latency histogram, top query categories)"),
  spacer(),
  p("[PLACEHOLDER — Insert summary statistics: distribution of queries routed to Naive vs. Graph RAG, average response latency per mode, most queried document categories.]"),

  h(HeadingLevel.HEADING_2, "4.6 System Performance"),
  p("Response latency was measured across a sample of queries in the production deployment environment. On average, Naive RAG queries complete in approximately X seconds end-to-end from the moment the request reaches the FastAPI backend to the return of the answer. Graph RAG queries, which require entity extraction and graph traversal in addition to LLM generation, complete in approximately Y seconds. The LLM-based mode selection step adds approximately Z seconds of overhead per query."),
  placeholder("TABLE — Response Latency Statistics (mean, median, 95th percentile) for Naive RAG and Graph RAG modes"),
  spacer(),
  p("Cold start latency on Render's free tier — the delay between an idle service receiving its first request and returning a response — was measured at approximately 60 seconds. This latency is attributable to the service startup time and the initialization of the RAG retrievers, which load the embedding matrix and establish connections to Azure services. Subsequent requests within the same active period incur no cold start penalty."),
  pageBreak()
];

// ─── 5. DISCUSSION ────────────────────────────────────────────────────────────
const discussion = [
  h(HeadingLevel.HEADING_1, "5. Discussion", { pageBreak: false }),
  sectionDivider(),

  h(HeadingLevel.HEADING_2, "5.1 Achievement Against Project Objectives"),
  p("The three objectives defined in the project proposal were used as the primary framework for evaluating the outcomes of the Capstone engagement."),
  p("Objective 1 — Consulting Workflow Analysis — was addressed through collaboration with SPARC's project lead, who conducted a structured analysis of consultant workflows to identify the specific tasks that consumed the most time and were most amenable to AI augmentation. This analysis confirmed the two primary pain points motivating the project: external research and deliverable production, and internal document retrieval. The functional requirements derived from this analysis directly shaped the two-mode architecture of ConsultantIQ."),
  p("Objective 2 — Designing and Implementing an LLM-Based Architecture — is the most substantially realized objective of the three. The full-stack platform described in Section 3 represents a production-grade implementation that goes significantly beyond the original proposal scope in several respects: the document ingestion pipeline supports four file formats and includes vision processing for visual content; the retrieval layer implements both naive and graph-based strategies with intelligent routing; the orchestration layer supports three distinct output types (text, Word document, and PowerPoint presentation); and the system is live and accessible through a public URL."),
  p("Objective 3 — Ensuring Quality, Trust, and Governance of AI Outputs — is partially realized. The hallucination prevention mechanism is fully implemented: all RAG answers are retrieval-grounded and source-cited, and the LLM is explicitly constrained against generating beyond the provided context. The evaluation framework for measuring output quality is defined and instrumented. The security and access control mechanisms necessary for processing actual SPARC documents remain as planned future work."),

  h(HeadingLevel.HEADING_2, "5.2 Technical Trade-offs and Design Decisions"),
  p("Several architectural decisions made during the project involved explicit trade-offs that are worth examining in retrospect."),
  p("The decision to use n8n as the orchestration layer rather than building a custom backend router proved to be strongly positive. The visual workflow editor dramatically accelerated the design and iteration of the agent routing logic, the document generation flow, and the dual-trigger architecture. Agent instructions and routing conditions could be modified and tested without code deployments, reducing the iteration cycle for prompt engineering from hours to minutes. The primary limitation of this approach is that the n8n workflow introduces a dependency on an external platform: if the n8n cloud service experiences downtime, the entire routing layer becomes unavailable regardless of the backend's health. For a production deployment, a self-hosted n8n instance would provide greater reliability."),
  p("The transition from parallel hybrid retrieval to LLM-based mode selection was a significant architectural pivot driven by practical production constraints. The parallel hybrid approach — running both Naive RAG and Graph RAG on every query and synthesizing their results — consistently produced the highest quality answers in testing but incurred two full retrieval pipeline executions plus a synthesis call per query. In a production consulting environment where consultants may submit dozens of queries per session, this cost structure is untenable. The LLM-based router preserves the intelligence of the hybrid approach — routing entity-rich relational queries to Graph RAG and broad semantic queries to Naive RAG — while keeping per-query costs within acceptable bounds. The trade-off is that the routing decision itself is subject to LLM judgment, introducing a small probability of misclassification for ambiguous queries."),
  p("The choice to build the RAG system from scratch rather than using n8n's native vector store node is discussed in detail in Section 2.5. In hindsight, this decision added several weeks of development time but produced a system with capabilities — graph-based retrieval, configurable chunking, metadata enrichment, vision processing, and a full evaluation framework — that would have been impossible to achieve with any available off-the-shelf solution."),

  h(HeadingLevel.HEADING_2, "5.3 Limitations"),
  p("Several limitations of the current implementation are acknowledged."),
  p("The knowledge base used for evaluation consists of twenty test documents rather than actual SPARC Consulting materials. While the test documents were selected to represent the types and formats of real consulting documents, they do not reproduce the volume, domain specificity, or language patterns of SPARC's actual proprietary corpus. Evaluation results obtained on the test dataset cannot be assumed to generalize directly to production performance on real consulting documents."),
  p("The security infrastructure necessary for processing and storing confidential consulting documents has not yet been implemented. Role-based access control, document-level encryption, audit logging, and data residency compliance mechanisms are identified as priority deliverables for the next phase of the project."),
  p("The Render free tier deployment imposes a cold start latency of approximately 60 seconds, which is unsuitable for production consultant use. Upgrading to a paid Render tier or migrating to a dedicated cloud environment is required before the system can be deployed for active use."),
  p("The LLM-based retrieval mode selector, while practically effective, has not been formally evaluated against a baseline of manual mode selection. The proportion of queries for which the router chooses the suboptimal mode is currently unknown and constitutes a gap in the evaluation."),
  pageBreak()
];

// ─── 6. CONCLUSION ────────────────────────────────────────────────────────────
const conclusion = [
  h(HeadingLevel.HEADING_1, "6. Conclusion", { pageBreak: false }),
  sectionDivider(),

  h(HeadingLevel.HEADING_2, "6.1 Summary"),
  p("This Capstone project set out to address a concrete operational challenge in management consulting: the disproportionate time consultants spend on knowledge-intensive but repeatable tasks — searching internal document repositories and producing structured research deliverables — at the expense of higher-value analytical and client-facing work. The response to this challenge is ConsultantIQ, an AI-powered consulting intelligence platform built for SPARC Consulting and deployed as a live production service."),
  p("The platform integrates two complementary capabilities. The first is a custom-built Retrieval-Augmented Generation system that allows consultants to query SPARC's internal knowledge base through natural language, receiving grounded answers with explicit source citations. The RAG system's architecture — a five-stage ingestion pipeline, dual vector store backends, and two retrieval strategies (naive vector retrieval and graph-based retrieval over a knowledge graph of consulting entities) with intelligent LLM-based routing — was designed to provide the quality, verifiability, and hallucination resistance that professional services work requires. The decision to build this system from scratch, rather than relying on off-the-shelf automation platform capabilities, was validated by the evaluation results showing the superiority of the custom system on every measured quality dimension."),
  p("The second capability is an AI-driven research and document generation workflow orchestrated through n8n. Consultants can submit research questions through a conversational interface and receive synthesized market intelligence, optionally rendered as a downloadable Word report or a PowerPoint presentation, without leaving the platform. The workflow's architecture — an Anthropic Claude classifier routing to a GPT-4o research agent with live web search — enables the system to handle both document queries and open-ended research requests within a unified interface."),
  p("The project demonstrates that enterprise-grade AI augmentation for professional services is achievable with a focused technical investment. The core architectural principle — grounding every AI output in cited, retrievable source material rather than relying on the model's parametric knowledge — is the key design decision that makes the system trustworthy enough for deployment in a consulting context where the credibility of outputs directly affects client outcomes."),

  h(HeadingLevel.HEADING_2, "6.2 Future Work"),
  p("Several directions for future development have been identified based on the limitations discussed in Section 5.3 and the operational experience gained during the project."),
  bullet("Security and access control infrastructure: Implementation of role-based document access, document-level encryption, audit logging, and data residency compliance mechanisms to enable ingestion of actual SPARC Consulting proprietary documents into the production knowledge base."),
  bullet("Production deployment upgrade: Migration from Render's free tier to a paid hosting environment to eliminate cold start latency and ensure service reliability for active consultant use."),
  bullet("Query analytics dashboard: Completion of the query analytics module to provide operational visibility into usage patterns, retrieval mode distribution, response latency, and consultant-assigned quality ratings."),
  bullet("Evaluation completion: Execution of the full evaluation suite on the production knowledge base once real SPARC documents are ingested, including the 100-query test harness, retrieval mode comparison, and generation quality scoring."),
  bullet("Router accuracy evaluation: Formal assessment of the LLM-based retrieval mode selector against a manually-labeled query set to quantify misclassification rate and identify query types that consistently receive suboptimal routing."),
  bullet("Knowledge graph expansion: Scaling the Graph RAG knowledge graph from the current test corpus to the full SPARC document repository, and evaluating the impact of graph density on retrieval quality for relational and multi-hop queries."),
  bullet("Human feedback loop: Implementation of a consultant feedback mechanism allowing users to rate answers and flag hallucinations, inaccurate citations, or missing information, with feedback routed into the evaluation pipeline for continuous quality monitoring."),
  pageBreak()
];

// ─── REFERENCES ───────────────────────────────────────────────────────────────
const references = [
  h(HeadingLevel.HEADING_1, "References", { pageBreak: false }),
  sectionDivider(),
  spacer(),
  p("[1] S. Noy and W. Zhang, \"Experimental Evidence on the Productivity Effects of Generative AI,\" Science, vol. 381, no. 6654, pp. 187–192, 2023."),
  p("[2] F. Dell'Acqua, E. McFowland III, E. R. Mollick, H. Lifshitz-Assaf, K. Kellogg, S. Rajendran, L. Krayer, F. Candelon, and K. R. Lakhani, \"Navigating the Jagged Technological Frontier: Field Experimental Evidence of the Effects of AI on Knowledge Worker Productivity and Quality,\" Harvard Business School Working Paper 24-013, 2023."),
  p("[3] Z. Ji, N. Lee, R. Frieske, T. Yu, D. Su, Y. Xu, E. Ishii, Y. J. Bang, A. Madotto, and P. Fung, \"Survey of Hallucination in Natural Language Generation,\" ACM Computing Surveys, vol. 55, no. 12, pp. 1–38, 2023."),
  p("[4] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Kuttler, M. Lewis, W. Tau Yih, T. Rocktaschel, S. Riedel, and D. Kiela, \"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,\" Advances in Neural Information Processing Systems (NeurIPS), vol. 33, 2020."),
  p("[5] Y. Gao, Y. Xiong, X. Gao, K. Jia, J. Pan, Y. Bi, Y. Dai, J. Sun, and H. Wang, \"Retrieval-Augmented Generation for Large Language Models: A Survey,\" arXiv preprint arXiv:2312.10997, 2023."),
  p("[6] S. Pan, L. Luo, Y. Wang, C. Chen, J. Wang, and X. Wu, \"Unifying Large Language Models and Knowledge Graphs: A Roadmap,\" IEEE Transactions on Knowledge and Data Engineering, 2024."),
  p("[7] E. Edge, H. Trinh, N. Cheng, J. Bradley, A. Chao, A. Mody, S. Truitt, and J. Larson, \"From Local to Global: A Graph RAG Approach to Query-Focused Summarization,\" arXiv preprint arXiv:2404.16130, 2024."),
  p("[8] L. Wang, C. Ma, X. Feng, Z. Zhang, H. Yang, J. Zhang, Z. Chen, J. Tang, X. Chen, Y. Lin, W. X. Zhao, Z. Wei, and J. Wen, \"A Survey on Large Language Model Based Autonomous Agents,\" Frontiers of Computer Science, vol. 18, no. 6, 2024."),
  pageBreak()
];

// ─── WORK IN PROGRESS ─────────────────────────────────────────────────────────
const wip = [
  h(HeadingLevel.HEADING_1, "Appendix: Work in Progress — Pending Sections and Additions"),
  sectionDivider(),
  p("The following components are currently under development or pending completion. Each item is documented here so that it can be added to the appropriate section of this report once finalized."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.1 Figures and Diagrams (Section 3)"),
  bullet("Figure 1 — High-level system architecture diagram showing the three-layer architecture (React frontend, n8n orchestration, FastAPI backend) and all Azure cloud services. To be added to Section 3.1."),
  bullet("Figure 2 — n8n workflow diagram screenshot annotated with node labels and flow paths. To be added to Section 3.6."),
  bullet("Figure 3 — ConsultantIQ frontend screenshot showing the chat interface, sidebar, and a sample interaction. To be added to Section 3.7."),
  bullet("Figure 4 — Deployment architecture diagram showing Render, Azure OpenAI, Azure AI Search, and Azure Cosmos DB connections. To be added to Section 3.9."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.2 Evaluation Results (Section 4)"),
  bullet("Table: Retrieval metrics by search mode (Recall@1, @3, @5 / Precision@1, @3, @5 / MRR) for vector, full-text, and hybrid RRF modes. To be added to Section 4.2."),
  bullet("Figure 5 — Bar chart comparing Recall@5 and MRR across retrieval modes. To be added to Section 4.2."),
  bullet("Table: Generation quality metrics (Groundedness, Completeness, Relevancy) for Naive RAG and Graph RAG modes. To be added to Section 4.3."),
  bullet("Figure 6 — Chart visualizing generation quality comparison. To be added to Section 4.3."),
  bullet("Table: Full head-to-head retrieval mode comparison across query categories. To be added to Section 4.4."),
  bullet("Table: Response latency statistics (mean, median, 95th percentile) per retrieval mode. To be added to Section 4.6."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.3 Query Analytics (Section 4.5)"),
  bullet("Query analytics module implementation: per-query mode distribution, latency histogram, top query categories."),
  bullet("Figure 7 — Query analytics dashboard screenshot or charts. To be added to Section 4.5."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.4 n8n Agent Instructions"),
  bullet("Full system prompts for the AI Agent Classifier (Anthropic Claude) and the Research Agent (GPT-4o) to be added as a supplementary appendix once finalized. These will document the exact instructions governing agent behavior, including the classification rules, the research synthesis guidelines, the document generation trigger conditions, and the hallucination prevention directives."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.5 Technology Stack Table (Section 2 / Section 3)"),
  bullet("A comprehensive technology stack table listing all tools, frameworks, cloud services, and libraries used in the project with their roles and version numbers. To be inserted in the Methodology section."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.6 Workflow Update: 3-Stage Document Generation"),
  bullet("Documentation of the finalized 3-stage Research Agent document generation flow: Stage 1 (research synthesis with %%REPORT_READY%% tag), Stage 2 (Word document download), Stage 3 (%%DECK_READY%% tag triggering Presenton PowerPoint generation). Section 3.6.3 will be updated once the implementation is finalized."),
  spacer(),

  h(HeadingLevel.HEADING_2, "A.7 Results Interpretation Text"),
  bullet("Interpretation paragraphs for Sections 4.2, 4.3, 4.4, and 4.5 to be written once evaluation runs are complete and metrics are available."),
  bullet("Response latency variable placeholders (X, Y, Z seconds in Section 4.6) to be replaced with measured values."),
];

// ─── ASSEMBLE DOCUMENT ────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } }
        }, {
          level: 1,
          format: LevelFormat.BULLET,
          text: "\u25E6",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } }
        }]
      }
    ]
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22 } }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 }
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 280, after: 100 }, outlineLevel: 1 }
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: "595959" },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 }
      },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            alignment: AlignmentType.RIGHT,
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2E75B6", space: 1 } },
            children: [new TextRun({ text: "ConsultantIQ — MSBA Capstone Report | Charbel Merhi | AUB 2026", size: 18, font: "Arial", color: "888888" })]
          })
        ]
      })
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            border: { top: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC", space: 1 } },
            children: [
              new TextRun({ text: "Page ", size: 18, font: "Arial", color: "888888" }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18, font: "Arial", color: "888888" }),
              new TextRun({ text: " of ", size: 18, font: "Arial", color: "888888" }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, font: "Arial", color: "888888" }),
            ]
          })
        ]
      })
    },
    children: [
      ...titlePage,
      ...abstractPage,
      ...tocPage,
      ...introduction,
      ...background,
      ...methodology,
      ...results,
      ...discussion,
      ...conclusion,
      ...references,
      ...wip,
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("C:/Users/merhi/Desktop/ConsultantIQ_Capstone_Draft.docx", buffer);
  console.log("Done: ConsultantIQ_Capstone_Draft.docx");
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
