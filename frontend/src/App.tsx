import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatArea } from './components/ChatArea';
import { AnalyticsPage } from './components/AnalyticsPage';
import { useChatHistory } from './hooks/useChatHistory';

type ActiveTab = 'chat' | 'analytics';

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('chat');
  const {
    conversations,
    activeConversation,
    activeId,
    setActiveId,
    createConversation,
    updateConversation,
    deleteConversation,
  } = useChatHistory();

  return (
    <div className="flex h-screen overflow-hidden w-full">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={(id) => { setActiveId(id); setActiveTab('chat'); }}
        onCreate={() => { createConversation(); setActiveTab('chat'); }}
        onDelete={deleteConversation}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      {activeTab === 'chat' ? (
        <ChatArea
          conversation={activeConversation}
          onUpdate={updateConversation}
          onNewChat={createConversation}
          onToggleSidebar={() => setSidebarOpen(true)}
        />
      ) : (
        <AnalyticsPage onToggleSidebar={() => setSidebarOpen(true)} />
      )}
    </div>
  );
}

export default App;
