import type { ChatMessage } from '../lib/types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { FileDownloadCard } from './FileDownloadCard';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end px-4 py-2">
        <div className="bg-navy text-white rounded-2xl rounded-br-sm px-4 py-2.5 max-w-[75%]">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 px-4 py-2">
      <div className="w-8 h-8 rounded-full bg-navy flex items-center justify-center shrink-0 mt-0.5">
        <span className="text-white text-xs font-bold">S</span>
      </div>
      <div className="max-w-[85%] space-y-2">
        {message.responseType === 'text' && (
          <div className="bg-white border border-sparc-border rounded-2xl rounded-bl-sm px-4 py-3">
            <MarkdownRenderer content={message.content} />
          </div>
        )}

        {message.responseType === 'file_download' && (
          <div className="space-y-2">
            <div className="bg-white border border-sparc-border rounded-2xl rounded-bl-sm px-4 py-3">
              <p className="text-sm text-sparc-text">Your report is ready for download.</p>
            </div>
            <FileDownloadCard
              fileName={message.fileName || 'ConsultantIQ_Report.docx'}
              downloadUrl={message.content}
              type="docx"
            />
          </div>
        )}

        {message.responseType === 'link_download' && (
          <div className="space-y-2">
            {message.content && (
              <div className="bg-white border border-sparc-border rounded-2xl rounded-bl-sm px-4 py-3">
                <MarkdownRenderer content={message.content} />
              </div>
            )}
            {message.downloadUrl && (
              <FileDownloadCard
                fileName={message.fileName || 'Presentation.pptx'}
                downloadUrl={message.downloadUrl}
                type="pptx"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
