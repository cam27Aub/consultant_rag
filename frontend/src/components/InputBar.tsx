import { useState, useRef, useCallback } from 'react';
import { SendHorizontal } from 'lucide-react';

interface InputBarProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }
  };

  return (
    <div className="border-t border-sparc-border bg-white px-4 py-3">
      <div className="w-full flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => { setText(e.target.value); handleInput(); }}
          onKeyDown={handleKeyDown}
          placeholder="Ask ConsultantIQ..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none border border-sparc-border rounded-xl px-4 py-2.5 text-sm text-sparc-text placeholder:text-sparc-muted focus:outline-none focus:border-navy focus:ring-1 focus:ring-navy disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="bg-navy text-white p-2.5 rounded-xl hover:bg-navy-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          <SendHorizontal className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
