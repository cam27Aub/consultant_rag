import { useState, useEffect, useRef } from 'react';
import { Plus, MessageSquare, Trash2, X, BarChart2, Pencil } from 'lucide-react';
import type { Conversation } from '../lib/types';
import { BRANDING } from '../constants/branding';

type ActiveTab = 'chat' | 'analytics';

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  isOpen: boolean;
  onClose: () => void;
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function Sidebar({
  conversations,
  activeId,
  onSelect,
  onCreate,
  onDelete,
  onRename,
  isOpen,
  onClose,
  activeTab,
  onTabChange,
}: SidebarProps) {
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 1024);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    if (editingId) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editingId]);

  const startEditing = (e: React.MouseEvent, convo: Conversation) => {
    e.stopPropagation();
    setEditingId(convo.id);
    setEditingTitle(convo.title);
  };

  const commitRename = () => {
    if (editingId && editingTitle.trim()) {
      onRename(editingId, editingTitle.trim());
    }
    setEditingId(null);
  };

  const cancelRename = () => {
    setEditingId(null);
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={onClose} />
      )}

      <aside
        className="fixed lg:static inset-y-0 left-0 z-50 w-72 bg-navy-dark text-white flex flex-col transition-transform duration-200 ease-in-out"
        style={{ translate: isOpen || isDesktop ? '0' : '-100%' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div>
            <h1 className="text-base font-bold tracking-tight">{BRANDING.appName}</h1>
            <p className="text-[11px] text-white/50 mt-0.5">{BRANDING.companyName}</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onCreate}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              title="New Chat"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors lg:hidden"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto py-2">
          {conversations.length === 0 && (
            <p className="text-xs text-white/30 text-center py-8">No conversations yet</p>
          )}
          {conversations.map((convo) => (
            <div
              key={convo.id}
              onClick={() => { if (editingId !== convo.id) { onSelect(convo.id); onClose(); } }}
              className={`
                group flex items-center gap-2 mx-2 px-3 py-2.5 rounded-lg cursor-pointer
                transition-colors text-sm
                ${activeId === convo.id ? 'bg-navy text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'}
              `}
            >
              <MessageSquare className="w-4 h-4 shrink-0 opacity-60" />

              {editingId === convo.id ? (
                <input
                  ref={inputRef}
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitRename();
                    if (e.key === 'Escape') cancelRename();
                    e.stopPropagation();
                  }}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 min-w-0 bg-white/10 text-white text-[13px] rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-white/30"
                />
              ) : (
                <div className="flex-1 min-w-0">
                  <p className="truncate text-[13px]">{convo.title}</p>
                  <p className="text-[10px] opacity-40 mt-0.5">{timeAgo(convo.updatedAt)}</p>
                </div>
              )}

              {editingId !== convo.id && (
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => startEditing(e, convo)}
                    className="p-1 rounded hover:bg-white/10 transition-colors"
                    title="Rename"
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(convo.id); }}
                    className="p-1 rounded hover:bg-white/10 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer — Analytics nav + branding */}
        <div className="p-3 border-t border-white/10 space-y-1">
          <button
            onClick={() => { onTabChange('analytics'); onClose(); }}
            className={`
              w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors
              ${activeTab === 'analytics'
                ? 'bg-navy text-white'
                : 'text-white/60 hover:bg-white/5 hover:text-white'}
            `}
          >
            <BarChart2 className="w-4 h-4 shrink-0" />
            <span className="text-[13px]">Analytics</span>
          </button>
          <p className="text-[10px] text-white/30 text-center pt-1">
            Powered by {BRANDING.companyName}
          </p>
        </div>
      </aside>
    </>
  );
}
