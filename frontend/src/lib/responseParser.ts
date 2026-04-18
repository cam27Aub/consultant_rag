import type { ParsedResponse } from './types';

function cleanSignalTags(text: string): string {
  return text.replace(/%%REPORT_READY%%/g, '').replace(/%%DECK_READY%%/g, '').trim();
}

function extractCtaOptions(text: string): { cleanText: string; options: string[] | null } {
  const match = text.match(/%%CTA%%([\s\S]*?)%%CTA_END%%/i);
  if (!match) return { cleanText: text, options: null };
  const options = match[1].split('|').map((o) => o.trim()).filter(Boolean);
  const cleanText = text.replace(match[0], '').trim();
  return { cleanText, options };
}

function extractFileName(disposition: string | null): string | null {
  if (!disposition) return null;
  const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
  return match ? match[1].replace(/['"]/g, '') : null;
}

export async function parseN8nResponse(response: Response): Promise<ParsedResponse> {
  const contentType = response.headers.get('content-type') || '';

  // Binary file response (.docx)
  if (
    contentType.includes('application/vnd.openxmlformats') ||
    contentType.includes('application/octet-stream')
  ) {
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const disposition = response.headers.get('content-disposition');
    const fileName = extractFileName(disposition) || 'ConsultantIQ_Report.docx';
    return { type: 'file_download', content: blobUrl, fileName };
  }

  // Text/JSON response
  let text: string;
  const rawText = await response.text();
  try {
    let data = JSON.parse(rawText);
    // Handle array responses (n8n returns arrays)
    if (Array.isArray(data)) data = data[0] || {};
    text = data.output || data.answer || data.text || data.response || data.message ||
      (typeof data === 'string' ? data : JSON.stringify(data));
  } catch {
    text = rawText;
  }

  // Check for PPTX download link
  const pptxUrlMatch = text.match(/https?:\/\/[^\s"'<>]+\.pptx[^\s"'<>]*/i);
  const hasDeckTag = text.includes('%%DECK_READY%%');

  if (pptxUrlMatch || hasDeckTag) {
    const cleanText = cleanSignalTags(text);
    return {
      type: 'link_download',
      content: cleanText,
      fileName: 'Presentation.pptx',
      downloadUrl: pptxUrlMatch ? pptxUrlMatch[0] : undefined,
    };
  }

  // CTA quick-reply buttons
  const { cleanText, options } = extractCtaOptions(text);
  if (options) {
    return { type: 'cta', content: cleanSignalTags(cleanText), ctaOptions: options };
  }

  // Plain text / markdown
  return { type: 'text', content: cleanSignalTags(text) };
}
