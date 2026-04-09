import { FileText, Presentation, Download } from 'lucide-react';

interface FileDownloadCardProps {
  fileName: string;
  downloadUrl: string;
  type: 'docx' | 'pptx';
}

export function FileDownloadCard({ fileName, downloadUrl, type }: FileDownloadCardProps) {
  const Icon = type === 'docx' ? FileText : Presentation;
  const label = type === 'docx' ? 'Word Document' : 'PowerPoint Presentation';

  return (
    <div className="flex items-center gap-3 bg-white border-l-4 border-l-navy border border-sparc-border rounded-lg p-4 max-w-sm">
      <Icon className="w-10 h-10 text-navy shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-sparc-text truncate">{fileName}</p>
        <p className="text-xs text-sparc-muted">{label}</p>
      </div>
      <a
        href={downloadUrl}
        download={fileName}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 bg-navy text-white text-xs font-medium px-3 py-2 rounded-lg hover:bg-navy-dark transition-colors shrink-0"
      >
        <Download className="w-3.5 h-3.5" />
        Download
      </a>
    </div>
  );
}
