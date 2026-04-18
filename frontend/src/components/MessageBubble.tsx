import { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { ChatMessage } from '../lib/types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { FileDownloadCard } from './FileDownloadCard';

interface MessageBubbleProps {
  message: ChatMessage;
  onCTAClick?: (option: string) => void;
}

export function MessageBubble({ message, onCTAClick }: MessageBubbleProps) {
  const [chosen, setChosen] = useState<string | null>(null);

  if (message.role === 'user') {
    return (
      <div className="flex justify-end py-2">
        <div className="bg-navy text-white rounded-2xl rounded-br-sm px-4 py-2.5 max-w-[75%]">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  const AssistantBubble = ({ children }: { children: React.ReactNode }) => (
    <div className="flex items-start gap-3 py-2">
      <div className="w-8 h-8 rounded-full bg-navy flex items-center justify-center shrink-0 mt-0.5">
        <span className="text-white text-xs font-bold">S</span>
      </div>
      <div className="flex-1 min-w-0 space-y-3">{children}</div>
    </div>
  );

  if (message.responseType === 'cta') {
    return (
      <AssistantBubble>
        <div className="bg-white border border-sparc-border rounded-2xl rounded-bl-sm px-4 py-3">
          <MarkdownRenderer content={message.content} />
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          {(message.ctaOptions ?? []).map((option) => {
            const isChosen = chosen === option;
            return (
              <button
                key={option}
                disabled={chosen !== null}
                onClick={() => {
                  setChosen(option);
                  onCTAClick?.(option);
                }}
                className={`
                  flex items-center gap-1.5 px-4 py-2 rounded-xl border text-sm font-medium transition-all
                  ${isChosen
                    ? 'bg-navy text-white border-navy cursor-default'
                    : chosen !== null
                      ? 'bg-white text-sparc-muted border-sparc-border cursor-not-allowed opacity-50'
                      : 'bg-white text-navy border-navy hover:bg-navy hover:text-white cursor-pointer'}
                `}
              >
                {isChosen && <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />}
                {option}
              </button>
            );
          })}
        </div>
      </AssistantBubble>
    );
  }

  return (
    <AssistantBubble>
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
    </AssistantBubble>
  );
}
