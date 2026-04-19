const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  TableOfContents
} = require("docx");
const fs = require("fs");

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const BLACK  = "000000";
const GRAY   = "595959";
const LGRAY  = "F2F2F2";
const DGRAY  = "404040";

const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const allBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

// Normal justified paragraph, 1.5 line spacing, 160 after
function p(text, opts = {}) {
  const runs = Array.isArray(text) ? text : [new TextRun({ text, size: 22, font: "Times New Roman", color: BLACK, bold: opts.bold || false, italics: opts.italic || false })];
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: opts.tight ? 80 : 180, line: 360 },
    children: Array.isArray(text) ? text : runs
  });
}

function pCenter(text) { return p(text, { center: true }); }

function run(text, opts = {}) {
  return new TextRun({ text, size: 22, font: "Times New Roman", color: BLACK, bold: opts.bold || false, italics: opts.italic || false, underline: opts.underline ? {} : undefined });
}

// Heading — plain black, bold, underlined like academic style
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 160 },
    children: [new TextRun({ text, size: 24, font: "Times New Roman", bold: true, color: BLACK })]
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, size: 22, font: "Times New Roman", bold: true, color: BLACK, underline: {} })]
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, size: 22, font: "Times New Roman", bold: true, italics: true, color: BLACK })]
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 100 },
    children: [new TextRun({ text, size: 22, font: "Times New Roman" })]
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    spacing: { after: 100 },
    children: [new TextRun({ text, size: 22, font: "Times New Roman" })]
  });
}

function spacer() { return new Paragraph({ spacing: { after: 120 }, children: [new TextRun("")] }); }
function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }

function figCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 200 },
    children: [new TextRun({ text, size: 20, font: "Times New Roman", italics: true, bold: true, color: DGRAY })]
  });
}

function placeholder(label) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 160 },
    border: {
      top:    { style: BorderStyle.DASHED, size: 6, color: "999999" },
      bottom: { style: BorderStyle.DASHED, size: 6, color: "999999" },
      left:   { style: BorderStyle.DASHED, size: 6, color: "999999" },
      right:  { style: BorderStyle.DASHED, size: 6, color: "999999" },
    },
    children: [new TextRun({ text: `[ ${label} ]`, size: 20, font: "Times New Roman", color: "888888", italics: true })]
  });
}

function hdrCell(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: allBorders,
    shading: { fill: "2E2E2E", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, size: 20, font: "Times New Roman", bold: true, color: "FFFFFF" })] })]
  });
}

function dataCell(text, w, opts = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: allBorders,
    shading: { fill: opts.fill || "FFFFFF", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT, children: [new TextRun({ text, size: 20, font: "Times New Roman", bold: opts.bold || false, color: opts.color || BLACK })] })]
  });
}

// ─── TITLE PAGE ──────────────────────────────────────────────────────────────
const titlePage = [
  spacer(), spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "AMERICAN UNIVERSITY OF BEIRUT", size: 28, font: "Times New Roman", bold: true, color: BLACK })] }),
  spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 480 },
    children: [new TextRun({ text: "ConsultantIQ: An AI-Powered Consulting Intelligence Platform", size: 32, font: "Times New Roman", bold: true, color: BLACK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "By", size: 22, font: "Times New Roman", italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 480 },
    children: [new TextRun({ text: "Charbel Merhi", size: 26, font: "Times New Roman", bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: "Advisor(s)", size: 22, font: "Times New Roman" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "Dr. Sirine Taleb", size: 22, font: "Times New Roman", bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 480 },
    children: [new TextRun({ text: "Dr. Ahmad El Hajj", size: 22, font: "Times New Roman", bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "A Capstone Project", size: 22, font: "Times New Roman", italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "submitted in partial fulfillment of the requirements", size: 22, font: "Times New Roman" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "for the degree of Master\u2019s in Business Analytics", size: 22, font: "Times New Roman" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "to the Suliman S. Olayan School of Business", size: 22, font: "Times New Roman" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "at the American University of Beirut", size: 22, font: "Times New Roman" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "Beirut, Lebanon", size: 22, font: "Times New Roman" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "April 2026", size: 22, font: "Times New Roman", bold: true })] }),
  spacer(),
  new Paragraph({ alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Prepared in collaboration with SPARC Consulting, Riyadh, Saudi Arabia", size: 20, font: "Times New Roman", italics: true, color: GRAY })] }),
  pageBreak()
];

// ─── ABSTRACT PAGE ───────────────────────────────────────────────────────────
const abstractPage = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text: "An Abstract of the Capstone Project of", size: 22, font: "Times New Roman", italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [
      new TextRun({ text: "Charbel Merhi", size: 22, font: "Times New Roman", bold: true }),
      new TextRun({ text: "  for  ", size: 22, font: "Times New Roman" }),
      new TextRun({ text: "Master\u2019s in Business Analytics (MSBA)", size: 22, font: "Times New Roman", bold: true }),
    ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 280 },
    children: [
      new TextRun({ text: "Title: ", size: 22, font: "Times New Roman", bold: true }),
      new TextRun({ text: "ConsultantIQ: An AI-Powered Consulting Intelligence Platform", size: 22, font: "Times New Roman" }),
    ] }),
  p("Management consulting is a knowledge-intensive profession in which significant consultant time is consumed by repeatable operational tasks: manually searching internal document repositories for relevant research and producing structured deliverables such as benchmarks, market reports, and PowerPoint presentations. These inefficiencies limit the volume of client work a firm can handle and introduce inconsistency in output quality."),
  p("This Capstone project addresses this challenge through the design and implementation of ConsultantIQ \u2014 a name in which IQ carries a dual meaning, referencing both the Intelligence Quotient metaphor of augmenting consultant capability and the platform\u2019s two core functions of Insights generation and knowledge-base Querying. The platform was developed in collaboration with SPARC Consulting, a Saudi-based management consulting firm, and integrates two complementary capabilities: a Retrieval-Augmented Generation system for querying the firm\u2019s internal document knowledge base, and an AI-driven research and document generation workflow for external research and deliverable production."),
  p("The RAG system was built from scratch as a multi-stage pipeline covering document ingestion, chunking, enrichment, embedding, and two retrieval strategies \u2014 naive vector retrieval and graph-based retrieval over a knowledge graph of consulting entities stored in Azure Cosmos DB. A large language model dynamically selects the appropriate retrieval strategy per query. The research workflow is orchestrated through n8n, where an Anthropic Claude classifier routes queries to either the RAG system or a GPT-4o research agent capable of live web search and automated generation of Word reports and PowerPoint presentations."),
  p("The platform is deployed live on Render and is accessible at consultantiq-api.onrender.com. A structured evaluation framework measuring retrieval quality and generation quality has been defined and will be presented upon completion. The project demonstrates that enterprise-grade AI augmentation for professional services requires purpose-built retrieval systems rather than off-the-shelf solutions to achieve grounded, verifiable, and hallucination-resistant outputs."),
  pageBreak()
];

// ─── TABLE OF CONTENTS ───────────────────────────────────────────────────────
const tocPage = [
  new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
  pageBreak()
];

// ─── 1. INTRODUCTION ─────────────────────────────────────────────────────────
const introduction = [
  h1("1. Introduction"),

  p("Management consulting is a knowledge-intensive profession in which value is created through the synthesis of information, the application of structured analytical frameworks, and the delivery of strategic recommendations to clients. Despite the high-level nature of this work, consultants at all seniority levels spend a significant proportion of their time on tasks that are operationally repetitive: manually searching through internal document repositories to locate relevant past research, aggregating information from external publications and market sources, and translating findings into polished client deliverables such as benchmark reports and PowerPoint presentations. Research has quantified the productivity cost of this pattern: Noy and Whitney (2023) demonstrated that professionals using generative AI tools completed knowledge-intensive writing tasks 37% faster while producing higher-quality outputs [1], and Dell\u2019Acqua et al. (2023) found in a field experiment with BCG consultants that AI assistance substantially lifted performance on complex analytical tasks [2]. These findings suggest that AI integration into consulting workflows is not a peripheral enhancement but a structural shift in how professional services firms can scale their intellectual output."),

  p("SPARC Consulting is a Saudi-based management consulting firm headquartered in Riyadh that specializes in helping organizations translate strategy into measurable results. The firm offers services spanning strategy development, strategy articulation and cascading, transformation acceleration, and decision-making support, and maintains an internal repository of proprietary documents accumulated across client engagements, including strategic reports, market analyses, benchmarking studies, proposal documents, and consulting frameworks."),

  p("A workflow analysis conducted by SPARC\u2019s project lead identified two distinct but related operational problems. The first is the external research and deliverable production problem: consultants regularly need to perform market research and competitive benchmarking as part of client engagements, a process that involves sourcing data from multiple external publications, synthesizing findings, and formatting outputs into Word reports or PowerPoint presentations \u2014 a time-consuming and fragmented process. The second is the internal knowledge retrieval problem: valuable institutional knowledge exists within SPARC\u2019s document repository, but locating relevant content requires manual browsing through unstructured files with no guarantee of completeness, meaning that proprietary research is systematically underutilized."),

  p("Prior attempts to address these challenges in the industry have relied largely on two categories of tools. General-purpose AI assistants such as Microsoft Copilot and ChatGPT can synthesize information and draft content, but they generate responses from parametric knowledge rather than a firm\u2019s proprietary documents, producing outputs that cannot be traced to authoritative sources and that carry a non-trivial risk of hallucination \u2014 a critical problem for a profession whose credibility rests on the accuracy of its deliverables [3]. Off-the-shelf automation platforms such as Zapier and n8n offer native vector store nodes that provide basic document querying, but these solutions are limited to naive vector similarity search with no support for structured reasoning across entity relationships, no configurable chunking or prompt engineering, and no mechanism for measuring output quality. Neither category of solution provides the grounded, source-cited, multi-strategy retrieval that a consulting knowledge base demands."),

  p("ConsultantIQ addresses this gap through a purpose-built architecture. Its novelty lies in three areas: first, a custom RAG engine implementing both naive vector retrieval and graph-based retrieval over a knowledge graph of consulting entities and their relationships, with a large language model dynamically selecting the appropriate strategy per query; second, an AI-driven research and document generation workflow that enables consultants to go from a natural language research request to a downloadable Word report or PowerPoint presentation without leaving a single interface; and third, a production evaluation framework measuring retrieval quality through Recall@K and Mean Reciprocal Rank and generation quality through groundedness, completeness, and relevancy scoring."),

  p("The contributions of this project are: (1) the design and implementation of a multi-stage RAG pipeline supporting four document formats with three chunking strategies, metadata enrichment, and optional visual content processing; (2) a Graph RAG system built on Azure Cosmos DB that models the consulting document corpus as a knowledge graph of business entities and relationships; (3) an LLM-based retrieval mode selector that dynamically routes queries to the most appropriate retrieval strategy; (4) an end-to-end AI research and document generation workflow orchestrated through n8n; and (5) a live production deployment accessible to SPARC consultants through a React web interface."),

  p("The project was structured around three objectives. The first objective was to analyze SPARC\u2019s consultant workflows to identify operational pain points and derive functional requirements for an AI assistant. The second objective was to design and implement a full-stack LLM-based platform covering document retrieval, research synthesis, and deliverable generation. The third objective was to define quality and governance mechanisms ensuring that AI outputs are grounded, verifiable, and enterprise-appropriate. The approach taken combines a custom Python-based RAG backend, an n8n automation workflow serving as the orchestration layer, and a React frontend, all deployed on Render\u2019s native runtime."),

  pageBreak()
];

// ─── 2. BACKGROUND AND RELATED WORK ──────────────────────────────────────────
const background = [
  h1("2. Background and Related Work"),

  p("A foundational limitation of large language models used in isolation is hallucination: the tendency to generate plausible-sounding but factually incorrect content, particularly when queried on topics outside their training data or on proprietary organizational knowledge. Ji et al. (2023) conducted a comprehensive survey of hallucination in natural language generation, documenting its prevalence across factual question answering, summarization, and dialogue tasks and cataloguing both the causes and the consequences of this phenomenon [3]. For a management consulting firm whose client deliverables must be factually defensible, hallucination is not an acceptable risk, and it motivates the core design principle of ConsultantIQ: every answer must be grounded in and traceable to retrieved source documents."),

  p("Retrieval-Augmented Generation was proposed by Lewis et al. (2020) as a framework that addresses the hallucination problem by conditioning language model generation on retrieved document passages [4]. In the original formulation, a retriever fetches relevant passages from a document store using query-document similarity, and these passages are prepended to the model\u2019s prompt as factual context. The model is instructed to answer using only the provided context, substantially reducing its reliance on potentially incorrect parametric knowledge. Gao et al. (2023) subsequently surveyed the growing landscape of RAG systems, organizing them into three architectural categories: naive RAG, which follows a straightforward retrieve-then-generate pipeline; advanced RAG, which introduces query rewriting and result re-ranking; and modular RAG, which decomposes the pipeline into independently configurable components [5]. ConsultantIQ implements elements across all three categories: naive retrieval as a baseline mode, query rewriting for follow-up questions in multi-turn conversations, and a fully modular pipeline with configurable chunking, enrichment, and retrieval strategies."),

  p("While vector similarity search is effective for broad semantic queries, it does not capture the structured relationships between business entities. When a consultant asks how a specific consulting framework connects to a set of performance metrics, or how a company\u2019s competitive positioning relates to its market entry strategy, answering correctly requires reasoning across a graph of relationships rather than simple proximity in embedding space. Pan et al. (2024) proposed a roadmap for unifying large language models with knowledge graphs, arguing that the two technologies are complementary: knowledge graphs provide structured, verifiable factual grounding while LLMs provide the natural language interface and reasoning capability [6]. Edge et al. (2024) at Microsoft introduced GraphRAG, a graph-based retrieval approach specifically designed for query-focused summarization over large document corpora, demonstrating that community-structured knowledge graphs enable synthesis across documents that naive vector retrieval consistently fails to achieve [7]. The Graph RAG component of ConsultantIQ draws on both works: entities and relationships are extracted from ingested documents and stored as a graph in Azure Cosmos DB, and breadth-first subgraph traversal is used to gather structured context at query time."),

  p("The concept of agentic AI \u2014 systems in which language models plan, use tools, and complete multi-step tasks autonomously \u2014 is central to the research and document generation capability of ConsultantIQ. Wang et al. (2024) surveyed LLM-based autonomous agents, characterizing them by their perception, memory, action, and planning capabilities and identifying task automation and tool use as the primary application categories [8]. In ConsultantIQ, this concept is instantiated through the n8n orchestration workflow, where an Anthropic Claude agent classifies user intent and routes requests, and a GPT-4o research agent autonomously decides when to invoke a web search tool, when to synthesize from retrieved context alone, and when to trigger document generation. The choice of n8n as the orchestration layer \u2014 rather than Python-native frameworks such as LangChain or CrewAI \u2014 was made because n8n provides a visual, low-code environment for designing agent logic and integrating with external APIs without requiring code deployments for changes to routing logic or agent instructions, significantly accelerating iteration speed."),

  p("A critical architectural decision in this project was whether to build the RAG system from scratch or to use a pre-built RAG capability offered by an automation platform. Off-the-shelf solutions such as n8n\u2019s native vector store node or Zapier\u2019s document query blocks can be configured in hours and require no infrastructure management. However, they are limited to naive vector similarity search with no support for graph-based retrieval, no configurable chunking strategies, minimal prompt engineering capability, no hallucination detection, and no evaluation pipeline. There is no mechanism to measure whether the answers they produce are grounded in retrieved documents, and the per-execution pricing model makes them economically unsuitable at the query volumes a consulting firm would generate."),

  p("The custom RAG system built for ConsultantIQ addresses each of these limitations. Three retrieval modes are available, including graph-based retrieval that is architecturally impossible with any off-the-shelf solution. Chunking is fully controlled across three strategies tunable per document type. Every system prompt at every stage of the pipeline is configurable. Hallucination prevention is enforced through explicit retrieval grounding and mandatory source citation. A full evaluation framework measures Recall@K, Mean Reciprocal Rank, groundedness, completeness, and relevancy. The engineering investment required to build this system is justified precisely because the consulting use case demands quality and verifiability that no available off-the-shelf solution can provide. Table 1 summarizes the comparison."),

  spacer(),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2400, 3480, 3480],
    rows: [
      new TableRow({ children: [ hdrCell("Dimension", 2400), hdrCell("ConsultantIQ Custom RAG", 3480), hdrCell("Off-the-Shelf (n8n / Zapier)", 3480) ] }),
      new TableRow({ children: [ dataCell("Retrieval modes", 2400, { bold: true, fill: LGRAY }), dataCell("Naive vector, Graph RAG, LLM-selected", 3480, { fill: LGRAY }), dataCell("Naive vector only", 3480, { fill: LGRAY, color: "AA0000" }) ] }),
      new TableRow({ children: [ dataCell("Chunking control", 2400, { bold: true }), dataCell("Full: fixed, sentence, semantic \u2014 tunable per document type", 3480), dataCell("None: black-box, not configurable", 3480, { color: "AA0000" }) ] }),
      new TableRow({ children: [ dataCell("Hallucination prevention", 2400, { bold: true, fill: LGRAY }), dataCell("Enforced: retrieval-grounded, source citations mandatory", 3480, { fill: LGRAY }), dataCell("None: LLM output passed directly to user", 3480, { fill: LGRAY, color: "AA0000" }) ] }),
      new TableRow({ children: [ dataCell("Evaluation pipeline", 2400, { bold: true }), dataCell("Full: Recall@K, MRR, Groundedness, Completeness, Relevancy", 3480), dataCell("None: no quality visibility", 3480, { color: "AA0000" }) ] }),
      new TableRow({ children: [ dataCell("Cost model", 2400, { bold: true, fill: LGRAY }), dataCell("Azure API costs only; no per-query platform fees", 3480, { fill: LGRAY }), dataCell("Per-execution charges; expensive at scale", 3480, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("Scalability", 2400, { bold: true }), dataCell("API-first: serves any integration", 3480), dataCell("Vendor lock-in; hard to migrate", 3480) ] }),
    ]
  }),
  figCaption("Table 1 \u2013 Custom RAG vs. Off-the-Shelf Automation Platforms"),
  pageBreak()
];

// ─── 3. METHODOLOGY ──────────────────────────────────────────────────────────
const methodology = [
  h1("3. Methodology"),

  h2("3.1 System Overview"),
  p("ConsultantIQ is organized around three interconnected layers that together form a complete AI platform for management consulting. The first is a React web application that serves as the consultant-facing conversational interface, supporting multi-turn dialogue, persistent session memory, and the rendering of text responses, downloadable file attachments, and presentation links. The second is an n8n automation workflow that acts as the central orchestration engine, receiving all requests from the frontend, classifying their intent, and routing them to the appropriate downstream agent or service. The third is a FastAPI backend that hosts the custom RAG engine, the Word document generation service, and the chat persistence layer. All three layers are deployed on Render\u2019s native Python runtime and communicate over HTTPS."),
  placeholder("FIGURE 1 \u2013 High-Level System Architecture (React frontend / n8n orchestration / FastAPI backend + Azure cloud services)"),
  p("The system supports two modes of interaction. In Research Mode, a consultant submits a research question or a request to produce a deliverable. The n8n workflow routes the request to a GPT-4o research agent that searches the web, synthesizes findings, and generates a Word report or PowerPoint presentation on demand. In RAG Mode, a consultant submits a question about SPARC\u2019s internal documents. The request is forwarded to the FastAPI backend, where the RAG engine retrieves relevant passages and generates a grounded, source-cited answer."),

  h2("3.2 Data"),
  p("The knowledge base used in the current implementation consists of twenty test documents curated to represent the types of materials present in SPARC Consulting\u2019s actual document repository. The documents span four categories: strategic reports, market benchmarking studies, consulting frameworks and methodologies, and proposal documents. The file formats covered include PDF, Microsoft Word (DOCX), PowerPoint (PPTX), and Excel (XLSX), reflecting the full range of formats in which consulting knowledge is typically stored. The test documents were selected to cover a representative range of content types: dense narrative text, structured tabular data, visual chart-heavy slides, and mixed-format documents. This diversity was essential for validating the multi-format ingestion pipeline and the optional visual content processing stage."),
  p("The decision to use test documents rather than SPARC\u2019s actual proprietary files was driven by security and data governance considerations. Client-facing consulting documents contain sensitive commercial and strategic information that requires role-based access controls, document-level encryption, and audit logging before they can be processed by a cloud-hosted system. The implementation of these security mechanisms has been identified as the primary objective for the next phase of the project, after which actual SPARC documents will be ingested."),

  h2("3.3 Document Ingestion Pipeline"),
  p("All documents pass through a five-stage pipeline before they can be queried. The pipeline is format-agnostic and is designed to maximize the information density of the stored chunks through enrichment and optional visual content processing."),

  h3("3.3.1 Document Cracking"),
  p("The first stage extracts raw content from uploaded files into structured PageUnit objects, each representing one page or slide and carrying both text and tabular content. For PDF documents, text and embedded tables are extracted page by page using pdfplumber. For PowerPoint files, slide text and table data are extracted using python-pptx. For Word documents, python-docx is used with heading-based section breaks to preserve document structure. For Excel files, openpyxl extracts sheet data as structured tabular rows."),

  h3("3.3.2 Chunking"),
  p("PageUnits are split into smaller ChunkUnit objects using one of three strategies. The fixed window chunker splits text into overlapping word-count windows, suited for uniform documents where structural boundaries are not meaningful. The sentence-boundary chunker groups sentences into chunks that respect sentence endings, preferred for narrative text and reports. The semantic chunker groups paragraphs based on Jaccard word overlap, creating chunks that align with topical boundaries within a document and performing best on structured documents and Excel sheets with labeled sections. Each ChunkUnit carries the chunk text, chunk index, source filename, document type, page number, and section heading."),

  h3("3.3.3 Chunk Enrichment"),
  p("Before embedding, each chunk is enriched with automatically computed metadata. A cleaned_text field is generated by removing boilerplate, normalizing whitespace, and correcting Unicode artifacts. Keywords are extracted using TF-based scoring, retaining the top eight terms of at least four characters filtered against a stopword list. An extractive summary selects the top two sentences by word frequency scoring. A project_tag field maps the chunk to one of seven domain categories: retail, digital, market entry, HR and policy, benchmarking, strategy, or general. File-level metadata including word count, table presence, and document date are also stored."),

  h3("3.3.4 Vision Processing"),
  p("An optional stage addresses the informational content present in charts, diagrams, and visually formatted tables that text extraction cannot capture. GPT-4o Vision analyzes each page of a PDF or PowerPoint file for visual elements and appends a natural language description to the chunk text \u2014 for example, a bar chart comparing EBITDA margins across five sectors from 2020 to 2024. This description is included in the embedding and is therefore searchable, ensuring visually communicated knowledge is accessible through the RAG system. The stage is applied selectively to document types where visual content is expected to be informative."),

  h3("3.3.5 Embedding"),
  p("The final ingestion stage converts the enriched text of each ChunkUnit into a dense vector representation using Azure OpenAI\u2019s text-embedding-3-large model, producing 3,072-dimensional embeddings. These vectors capture the semantic meaning of each chunk and are used at query time for cosine similarity search."),

  h2("3.4 Storage and Retrieval"),
  p("Embedded chunks are stored in one of two backends depending on the environment. In local development, an in-memory store with disk persistence is used: chunk metadata is saved as JSON and the embedding matrix is stored as a NumPy binary array. Three search methods are available: vector search using cosine similarity, full-text search using TF-IDF cosine similarity, and hybrid search combining both through Reciprocal Rank Fusion with the formula 1 / (60 + rank + 1) per source. In production, Azure AI Search hosts the index with HNSW approximate nearest-neighbor search for the vector field, BM25 full-text search with a Lucene analyzer, and hybrid search combining both with Azure\u2019s built-in semantic reranking."),
  p("Three retrieval strategies are implemented. The Naive RAG retriever, for each incoming question, first detects whether the question is a follow-up in a multi-turn conversation and rewrites it to be self-contained if necessary \u2014 for example, rewriting \u201cWhat about their margins?\u201d to \u201cWhat are Company X\u2019s EBITDA margins?\u201d given the conversation history. The (possibly rewritten) question is then embedded and the top-k most relevant chunks are retrieved. GPT-4o receives the chunks as context alongside a system prompt that enforces grounded generation: it must cite sources using the format [Source: filename, section, Page N] and must explicitly state when the knowledge base does not contain relevant information rather than fabricating an answer."),
  p("The Graph RAG system models the document corpus as a knowledge graph of consulting entities and their relationships, stored in Azure Cosmos DB using the Gremlin API. At ingestion time, GPT-4o extracts structured entities and relationships from each chunk at temperature 0.0 for deterministic output. Entity types include consulting frameworks and models, metrics and KPIs, companies and organizations, roles and processes, and abstract concepts. Relationship types include HAS_COMPONENT, USED_IN, MEASURES, PART_OF, LEADS_TO, CONTRADICTS, SUPPORTS, REQUIRES, and DEFINES. At query time, key entity terms are extracted from the question, matched to graph vertices using a weighted scoring system, and a breadth-first traversal to depth two gathers a structured subgraph as context for the LLM."),
  p("An initial implementation ran both retrievers in parallel on every query and synthesized their results, producing the highest quality answers in testing. However, this approach was operationally unsuitable for production: the cost of two full retrieval executions plus a synthesis call per query, combined with the resulting latency, made it infeasible at the query volumes consulting work generates. The final architecture delegates the routing decision to the language model itself. A routing prompt sent to GPT-4o describes the characteristics of each retrieval mode and instructs the model to select the appropriate strategy for the query. This preserves the intelligence of the hybrid approach while keeping per-query cost and latency within production-acceptable bounds."),

  h2("3.5 n8n Orchestration Workflow"),
  p("The orchestration layer is implemented as an n8n workflow serving as the central routing engine for all user interactions. n8n is an open-source workflow automation platform that supports visual workflow design, HTTP API integration, and AI agent nodes, allowing routing logic and agent instructions to be iterated without backend code deployments."),
  placeholder("FIGURE 2 \u2013 n8n Workflow Diagram (dual triggers, AI Agent classifier, Switch node, Research Agent with Serper tool and MongoDB memory, If Report node, If Presentation node, Presenton, RAG Agent, four Respond-to-Webhook nodes)"),
  p("The workflow supports two entry points. The production trigger is a Webhook node receiving POST requests from the React frontend, with a body containing the user\u2019s message and a UUID session identifier. The testing trigger is n8n\u2019s built-in chat node for direct workflow testing. Because the two triggers expose different JSON structures, all downstream nodes use JavaScript try-catch expressions to read the payload from either path, ensuring identical behavior regardless of which trigger activated the workflow."),
  p("The first processing node is an AI Agent powered by Anthropic Claude whose sole function is to classify the incoming message as either RESEARCH or RAG. It is connected to a Simple Memory sub-node providing recent session context. The agent\u2019s system prompt was iteratively hardened to enforce a single-word output, as early iterations produced natural language explanations that caused the downstream Switch node to fail. A Switch node reads the classification and routes accordingly."),
  p("The Research Agent is a GPT-4o AI Agent node equipped with a Serper HTTP Request tool for live Google Search queries and a MongoDB Chat Memory sub-node connected to Azure Cosmos DB for full conversation history. The agent supports a three-stage document generation flow. In the first stage, the agent produces a structured research report and appends the signal tag %%REPORT_READY%% to its output; a downstream If node detects this and triggers an HTTP POST to the FastAPI backend\u2019s document generation endpoint, which streams back a binary Word file. In the second stage, the consultant may request a PowerPoint based on the report; the agent appends %%DECK_READY%% and a downstream If node triggers the Presenton API, which generates a presentation asynchronously and returns a download link. Plain research responses without a document request exit through a third Respond-to-Webhook node, and RAG responses exit through a fourth, giving four distinct exit paths in total. The RAG Agent is a simple HTTP Request node that forwards the query to the FastAPI backend\u2019s POST /query endpoint and returns the grounded answer with source citations."),

  h2("3.6 Technology Stack"),
  spacer(),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2600, 2800, 3960],
    rows: [
      new TableRow({ children: [ hdrCell("Component", 2600), hdrCell("Technology", 2800), hdrCell("Role", 3960) ] }),
      new TableRow({ children: [ dataCell("LLM \u2014 Reasoning", 2600, { fill: LGRAY }), dataCell("Azure OpenAI GPT-4o", 2800, { fill: LGRAY }), dataCell("Research agent, RAG generation, entity extraction, mode selection", 3960, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("LLM \u2014 Classification", 2600), dataCell("Anthropic Claude", 2800), dataCell("Query intent classification (RESEARCH vs RAG)", 3960) ] }),
      new TableRow({ children: [ dataCell("Embeddings", 2600, { fill: LGRAY }), dataCell("Azure OpenAI text-embedding-3-large", 2800, { fill: LGRAY }), dataCell("3,072-dim chunk and query vectors", 3960, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("Vector store (prod)", 2600), dataCell("Azure AI Search", 2800), dataCell("HNSW vector search, BM25 full-text, hybrid reranking", 3960) ] }),
      new TableRow({ children: [ dataCell("Knowledge graph", 2600, { fill: LGRAY }), dataCell("Azure Cosmos DB (Gremlin API)", 2800, { fill: LGRAY }), dataCell("Entity and relationship graph for Graph RAG", 3960, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("Chat memory", 2600), dataCell("Azure Cosmos DB (MongoDB API)", 2800), dataCell("Persistent conversation history for Research Agent", 3960) ] }),
      new TableRow({ children: [ dataCell("Orchestration", 2600, { fill: LGRAY }), dataCell("n8n", 2800, { fill: LGRAY }), dataCell("Workflow routing, agent coordination, document generation triggers", 3960, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("Web search", 2600), dataCell("Serper (Google Search API)", 2800), dataCell("Live external research for Research Agent", 3960) ] }),
      new TableRow({ children: [ dataCell("Presentation generation", 2600, { fill: LGRAY }), dataCell("Presenton API", 2800, { fill: LGRAY }), dataCell("Automated PowerPoint creation from research content", 3960, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("Backend", 2600), dataCell("FastAPI (Python)", 2800), dataCell("RAG API, document generation endpoint, chat persistence", 3960) ] }),
      new TableRow({ children: [ dataCell("Frontend", 2600, { fill: LGRAY }), dataCell("React + TypeScript (Vite)", 2800, { fill: LGRAY }), dataCell("Conversational UI, session management, file downloads", 3960, { fill: LGRAY }) ] }),
      new TableRow({ children: [ dataCell("Deployment", 2600), dataCell("Render (native Python runtime)", 2800), dataCell("Live at consultantiq-api.onrender.com", 3960) ] }),
    ]
  }),
  figCaption("Table 2 \u2013 ConsultantIQ Technology Stack"),

  h2("3.7 Frontend and Backend"),
  p("The React frontend presents a multi-session chat layout with a sidebar listing conversation history and a main area displaying the active conversation. Each conversation is assigned a UUID at creation time used as the session identifier sent to n8n, which maps it to the corresponding MongoDB Chat Memory thread. Conversation history is persisted to Azure Cosmos DB via the FastAPI backend and synchronized with a 500-millisecond debounce on every update. The response parser handles three distinct formats: binary Word documents detected by content-type header, streamed as downloadable Blob URLs and displayed as file cards; PowerPoint links detected by the presence of a .pptx URL or the %%DECK_READY%% signal tag; and text or Markdown responses rendered with full formatting support."),
  placeholder("FIGURE 3 \u2013 ConsultantIQ Frontend Screenshot (chat interface with sidebar, message area, and file download card)"),
  p("The FastAPI backend exposes the primary POST /query endpoint, which invokes the LLM-based mode selector, executes the selected retriever, captures stdout to detect the retrieval mode chosen, extracts source citations via regex pattern matching, strips internal debug output, and returns a clean JSON response containing the answer, the mode used, and source references. A document generation sub-application mounted at /docx converts Markdown-formatted research content into a formatted Word document streamed as a binary response. Chat persistence endpoints handle conversation listing, retrieval, creation, update, and deletion, all backed by Azure Cosmos DB."),

  h2("3.8 Deployment"),
  p("The application is deployed on Render using its native Python runtime. The FastAPI application is served by uvicorn on the port injected by Render\u2019s environment, and the React frontend\u2019s static build is served as a Single Page Application through a catch-all route in FastAPI. The live deployment is accessible at https://consultantiq-api.onrender.com. The deployment currently uses Render\u2019s free tier, which causes the service to sleep after fifteen minutes of inactivity and requires approximately sixty seconds to cold-start on the first request. All Azure service credentials are stored as environment variables in Render\u2019s configuration dashboard and are not present in the codebase."),

  pageBreak()
];

// ─── 4. RESULTS & DISCUSSION ──────────────────────────────────────────────────
const resultsDiscussion = [
  h1("4. Results & Discussion"),

  h2("4.1 System Outcomes"),
  p("The primary outcome of this project is a fully deployed, end-to-end AI platform accessible at https://consultantiq-api.onrender.com. The system successfully delivers both of its intended capabilities: grounded internal document querying through the RAG engine and AI-driven external research with automated deliverable generation through the n8n workflow. Each major system component was verified through functional testing on the twenty-document test knowledge base."),
  p("The RAG engine correctly processes queries across all four supported document formats. For a representative factual query such as \u201cWhat are the key components of the benchmarking framework in the strategy report?\u201d, the system retrieves the relevant chunks, identifies the source document and page numbers, and returns a structured answer with explicit source citations in the format [Source: filename, section, Page N]. When a query falls outside the knowledge base, the system correctly responds that the information is not available rather than fabricating an answer, validating the hallucination prevention mechanism."),
  p("The LLM-based retrieval mode selector routes queries appropriately based on their nature. Entity-dense relational queries such as \u201cHow does Porter\u2019s Five Forces connect to market entry strategy?\u201d are routed to Graph RAG, which traverses the entity relationship graph to gather structured context. Broad descriptive queries such as \u201cSummarize the findings of the digital transformation report\u201d are routed to Naive RAG, which retrieves the most semantically similar passages. This routing behavior was consistently observed across the test query set, confirming that the LLM classifier correctly distinguishes between query types without requiring manual mode specification from the user."),
  p("The Research Agent successfully conducts multi-turn research conversations with live web search. When a user requests market analysis on a specific industry, the agent invokes the Serper web search tool, synthesizes the retrieved results with its own analytical framing, and returns a structured research summary. When subsequently asked to produce a report, the agent appends the %%REPORT_READY%% signal tag and the n8n workflow automatically generates and streams a formatted Word document back to the frontend, where it appears as a downloadable file card. The three-stage document generation flow \u2014 research synthesis, Word report download, and PowerPoint generation via Presenton \u2014 was validated end-to-end."),
  placeholder("FIGURE 4 \u2013 Sample RAG Query and Response (showing source citations and retrieval mode used)"),
  placeholder("FIGURE 5 \u2013 Sample Research Query with Generated Word Document Download Card"),

  h2("4.2 Evaluation Framework and Preliminary Results"),
  p("A structured evaluation framework was designed to assess system quality across two dimensions. Retrieval quality is measured using three standard information retrieval metrics applied to a golden dataset of question-answer pairs: Recall@K (the proportion of queries for which at least one ground-truth document appears in the top K results, evaluated at K = 1, 3, and 5), Precision@K (the proportion of the top K results that are ground-truth relevant), and Mean Reciprocal Rank (the average of the reciprocal rank of the first relevant result across all queries). These metrics are computed independently for vector search, full-text search, and hybrid RRF search modes to enable objective comparison."),
  p("Generation quality is assessed through a judge-LLM approach in which GPT-4o evaluates each generated answer on three dimensions scored from zero to one: groundedness (whether the answer\u2019s claims are supported by the retrieved context), completeness (whether the answer addresses all aspects of the question given the available context), and relevancy (whether the answer directly addresses the question without irrelevant content). A 100-query test harness provides the query load for both evaluation phases. The evaluation is currently being executed on the test knowledge base and the results will be incorporated into this report upon completion."),
  placeholder("TABLE 3 \u2013 Retrieval Evaluation Results: Recall@1, @3, @5 / Precision@1, @3, @5 / MRR for Vector, Full-Text, and Hybrid RRF modes"),
  placeholder("FIGURE 6 \u2013 Retrieval Mode Comparison Chart (Recall@5 and MRR across the three search modes)"),
  placeholder("TABLE 4 \u2013 Generation Quality Results: Groundedness, Completeness, Relevancy for Naive RAG and Graph RAG"),
  p("[PLACEHOLDER \u2014 Insert result interpretation: which retrieval mode performs best, how groundedness scores validate the hallucination prevention mechanism, and which query categories show the largest performance gap between Naive RAG and Graph RAG.]"),

  h2("4.3 System Performance"),
  p("Response latency was measured across a sample of queries in the production deployment environment. Naive RAG queries complete in approximately [X] seconds end-to-end from the moment the request reaches the FastAPI backend to the return of a grounded answer. Graph RAG queries, which require entity term extraction, graph traversal, and LLM generation, complete in approximately [Y] seconds. The LLM-based routing step adds approximately [Z] seconds of overhead per query."),
  placeholder("TABLE 5 \u2013 Response Latency Statistics: Mean, Median, and 95th Percentile for Naive RAG and Graph RAG modes"),
  p("Cold start latency on Render\u2019s free tier \u2014 the delay from an idle service receiving its first request to returning a response \u2014 was measured at approximately sixty seconds. This latency is attributable to service startup time and retriever initialization, which loads the embedding matrix and establishes connections to Azure services. Subsequent requests within the same active window incur no cold start penalty. This behavior is acceptable for the current demonstration phase but must be addressed by upgrading to a paid hosting tier before the platform is deployed for active consultant use."),

  h2("4.4 Discussion"),
  p("The three objectives defined in the project proposal provide the primary lens for evaluating outcomes. Objective 1 \u2014 consulting workflow analysis \u2014 was addressed through the structured workflow analysis conducted by SPARC\u2019s project lead, which identified the two operational pain points that motivated the project architecture and confirmed the functional requirements. Objective 2 \u2014 designing and implementing an LLM-based architecture \u2014 is the most substantially realized objective, producing a production-grade full-stack platform that exceeds the original proposal scope in several respects: the ingestion pipeline supports four file formats including visual content processing, the retrieval layer implements two strategies with intelligent routing, and the platform generates three types of deliverables. Objective 3 \u2014 ensuring quality, trust, and governance \u2014 is partially realized: hallucination prevention and source citation are fully implemented, the evaluation framework is defined and instrumented, and the security infrastructure for processing actual SPARC documents is identified as the primary remaining deliverable."),
  p("The decision to build the RAG system from scratch rather than using off-the-shelf automation tools proved to be the correct architectural choice. The capabilities that differentiate ConsultantIQ \u2014 graph-based retrieval over a consulting entity knowledge graph, configurable chunking strategies, metadata-enriched vector search, and an objective evaluation framework \u2014 are not available in any current automation platform. The consulting use case specifically requires outputs whose accuracy can be verified by reference to source documents, and no platform that processes documents as a black box and returns answers without provenance tracing is suitable for this requirement."),
  p("The transition from parallel hybrid retrieval to LLM-based mode selection was a significant architectural pivot driven by production constraints. The parallel approach consistently produced the highest quality answers in testing but incurred two full retrieval pipeline executions plus a synthesis call per query, making it economically and operationally unsuitable. The LLM-based router preserves the intelligence of the hybrid approach at a fraction of the cost, with the trade-off that routing decisions are subject to LLM judgment and carry a small probability of misclassification for ambiguous queries."),
  p("From a company perspective, ConsultantIQ directly addresses the two operational pain points identified in the workflow analysis. The time spent on manual external research and deliverable formatting is reduced to a conversation: a consultant can go from a research question to a downloadable Word report in a single session. The institutional knowledge locked in SPARC\u2019s document repository becomes queryable through natural language, with every answer traceable to specific source documents and pages. Both capabilities are designed to augment rather than replace consultant judgment: the system provides grounded information and structured drafts, while the consultant applies domain expertise to interpret, refine, and present the findings."),
  p("Several limitations of the current implementation should be noted. The knowledge base consists of twenty test documents rather than SPARC\u2019s actual proprietary corpus, and evaluation results on the test dataset cannot be assumed to generalize directly to production performance. The security infrastructure for real document ingestion is not yet in place. The cold start latency on Render\u2019s free tier is unsuitable for active consultant use. The proportion of queries for which the LLM routing step selects the suboptimal retrieval mode has not been formally measured. These limitations are all addressed in the planned future work described in the Conclusion."),

  pageBreak()
];

// ─── 5. CONCLUSION ───────────────────────────────────────────────────────────
const conclusion = [
  h1("5. Conclusion"),
  p("This Capstone project set out to address two concrete operational inefficiencies in management consulting: the time consultants spend on manual external research and deliverable production, and the underutilization of institutional knowledge locked in internal document repositories. The response is ConsultantIQ, an AI-powered consulting intelligence platform built for SPARC Consulting and deployed as a live production service. The platform delivers both capabilities within a single conversational interface: a custom-built RAG system that answers natural language queries grounded in cited internal documents, and an AI-driven research and document generation workflow that produces Word reports and PowerPoint presentations from live web research."),
  p("The core architectural contributions of this project are a five-stage document ingestion pipeline supporting four file formats with three chunking strategies and optional visual content processing; a Graph RAG system over an Azure Cosmos DB knowledge graph of consulting entities and relationships; an LLM-based retrieval mode selector that dynamically routes queries between naive and graph retrieval; and an n8n orchestration workflow connecting a Claude intent classifier, a GPT-4o research agent, and three document output formats. The decision to build the RAG system from scratch rather than relying on off-the-shelf automation capabilities was validated by the quality, verifiability, and measurability requirements of the consulting use case, which no available platform could satisfy."),
  p("The platform is live and accessible at https://consultantiq-api.onrender.com. Evaluation results will be incorporated upon completion of the 100-query assessment currently underway. Several directions for future development have been identified: the implementation of security and access control infrastructure enabling ingestion of actual SPARC documents; an upgrade from Render\u2019s free tier to a production hosting environment; the completion of the query analytics module; a formal evaluation of the LLM routing classifier\u2019s accuracy; scaling the knowledge graph to the full SPARC document corpus; and the implementation of a consultant feedback loop for continuous quality monitoring."),
  spacer(),
  p("Acknowledgments", { bold: true }),
  p("The author would like to express sincere gratitude to Dr. Sirine Taleb and Dr. Ahmad El Hajj for their supervision and guidance throughout this Capstone project. Special thanks are extended to Antoinette Mouawad and the team at SPARC Consulting for their collaboration, domain expertise, and continued support in shaping the platform around real consulting needs."),
  pageBreak()
];

// ─── 6. REFERENCES ───────────────────────────────────────────────────────────
const references = [
  h1("6. References"),
  spacer(),
  p("[1] S. Noy and W. Zhang, \u201cExperimental Evidence on the Productivity Effects of Generative AI,\u201d Science, vol. 381, no. 6654, pp. 187\u2013192, 2023."),
  p("[2] F. Dell\u2019Acqua, E. McFowland III, E. R. Mollick, H. Lifshitz-Assaf, K. Kellogg, S. Rajendran, L. Krayer, F. Candelon, and K. R. Lakhani, \u201cNavigating the Jagged Technological Frontier: Field Experimental Evidence of the Effects of AI on Knowledge Worker Productivity and Quality,\u201d Harvard Business School Working Paper 24-013, 2023."),
  p("[3] Z. Ji, N. Lee, R. Frieske, T. Yu, D. Su, Y. Xu, E. Ishii, Y. J. Bang, A. Madotto, and P. Fung, \u201cSurvey of Hallucination in Natural Language Generation,\u201d ACM Computing Surveys, vol. 55, no. 12, pp. 1\u201338, 2023."),
  p("[4] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. K\u00fcttler, M. Lewis, W. Tau Yih, T. Rockt\u00e4schel, S. Riedel, and D. Kiela, \u201cRetrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,\u201d Advances in Neural Information Processing Systems (NeurIPS), vol. 33, 2020."),
  p("[5] Y. Gao, Y. Xiong, X. Gao, K. Jia, J. Pan, Y. Bi, Y. Dai, J. Sun, and H. Wang, \u201cRetrieval-Augmented Generation for Large Language Models: A Survey,\u201d arXiv preprint arXiv:2312.10997, 2023."),
  p("[6] S. Pan, L. Luo, Y. Wang, C. Chen, J. Wang, and X. Wu, \u201cUnifying Large Language Models and Knowledge Graphs: A Roadmap,\u201d IEEE Transactions on Knowledge and Data Engineering, 2024."),
  p("[7] E. Edge, H. Trinh, N. Cheng, J. Bradley, A. Chao, A. Mody, S. Truitt, and J. Larson, \u201cFrom Local to Global: A Graph RAG Approach to Query-Focused Summarization,\u201d arXiv preprint arXiv:2404.16130, 2024."),
  p("[8] L. Wang, C. Ma, X. Feng, Z. Zhang, H. Yang, J. Zhang, Z. Chen, J. Tang, X. Chen, Y. Lin, W. X. Zhao, Z. Wei, and J. Wen, \u201cA Survey on Large Language Model Based Autonomous Agents,\u201d Frontiers of Computer Science, vol. 18, no. 6, 2024."),
  pageBreak()
];

// ─── 7. APPENDIX — WORK IN PROGRESS ──────────────────────────────────────────
const appendix = [
  h1("7. Appendix \u2014 Planned Enhancements and Pending Additions"),
  p("The following items are currently under development or pending completion. Each is documented here with the section of the report to which it belongs, so that it can be incorporated upon finalization."),
  spacer(),
  h2("Figures and Diagrams (Section 3)"),
  bullet("Figure 1 \u2014 High-level system architecture diagram (three-layer: React / n8n / FastAPI + Azure services). To be added to Section 3.1."),
  bullet("Figure 2 \u2014 Annotated n8n workflow diagram screenshot. To be added to Section 3.5."),
  bullet("Figure 3 \u2014 ConsultantIQ frontend screenshot. To be added to Section 3.7."),
  spacer(),
  h2("Evaluation Results (Section 4.2)"),
  bullet("Table 3 \u2014 Retrieval evaluation metrics by search mode. To be added to Section 4.2."),
  bullet("Figure 6 \u2014 Retrieval mode comparison chart. To be added to Section 4.2."),
  bullet("Table 4 \u2014 Generation quality metrics. To be added to Section 4.2."),
  bullet("Table 5 \u2014 Response latency statistics. To be added to Section 4.3."),
  bullet("Result interpretation paragraphs and latency values [X], [Y], [Z] in Section 4.3."),
  spacer(),
  h2("Query Analytics (Section 4.2)"),
  bullet("Query analytics module: per-query mode distribution, latency histogram, top query categories."),
  bullet("Figure 7 \u2014 Query analytics dashboard screenshot or charts."),
  spacer(),
  h2("n8n Agent Instructions"),
  bullet("Full system prompts for the AI Agent Classifier (Anthropic Claude) and Research Agent (GPT-4o) to be added as a supplementary appendix once finalized."),
  spacer(),
  h2("3-Stage Document Generation Workflow"),
  bullet("Final documentation of the Research Agent\u2019s three-stage flow (research synthesis \u2192 Word document \u2192 Presenton PowerPoint) to update Section 3.5 once the implementation is finalized."),
];

// ─── ASSEMBLE DOCUMENT ────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } } }
      ]},
      { reference: "numbers", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }
      ]},
    ]
  },
  styles: {
    default: { document: { run: { font: "Times New Roman", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Times New Roman", color: BLACK },
        paragraph: { spacing: { before: 400, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Times New Roman", color: BLACK },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, italics: true, font: "Times New Roman", color: BLACK },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "AAAAAA", space: 1 } },
          children: [new TextRun({ text: "ConsultantIQ \u2014 MSBA Capstone | Charbel Merhi | AUB 2026", size: 18, font: "Times New Roman", color: GRAY })]
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC", space: 1 } },
          children: [
            new TextRun({ children: [PageNumber.CURRENT], size: 18, font: "Times New Roman", color: GRAY }),
          ]
        })
      ]})
    },
    children: [
      ...titlePage,
      ...abstractPage,
      ...tocPage,
      ...introduction,
      ...background,
      ...methodology,
      ...resultsDiscussion,
      ...conclusion,
      ...references,
      ...appendix,
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("C:/Users/merhi/Desktop/ConsultantIQ_Capstone_Draft_v2.docx", buf);
  console.log("Done: ConsultantIQ_Capstone_Draft_v2.docx");
}).catch(err => { console.error(err); process.exit(1); });
