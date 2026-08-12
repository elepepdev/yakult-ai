import { useState, useCallback, useEffect } from 'react';
import { wsService } from '@/services/websocket-service';

export interface ApprovalRequest {
  approval_id: string;
  tool_name: string;
  operation: 'write' | 'delete';
  path: string;
  diff?: string;
  exists?: boolean;
  is_dir?: boolean;
  size?: number;
  content_preview?: string;
}

export function useApprovalFloating() {
  const [requests, setRequests] = useState<ApprovalRequest[]>([]);

  useEffect(() => {
    const subscription = wsService.onMessage((message) => {
      if (message?.type === 'tool-approval-request') {
        const req: ApprovalRequest = {
          approval_id: message.approval_id || '',
          tool_name: message.tool_name || '',
          operation: (message.operation === 'delete' ? 'delete' : 'write'),
          path: message.path || '',
          diff: message.diff || undefined,
          exists: message.exists,
          is_dir: message.is_dir,
          size: message.size,
          content_preview: message.content_preview,
        };
        setRequests((prev) => [...prev, req]);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const respond = useCallback((approvalId: string, approved: boolean) => {
    wsService.sendMessage({
      type: 'tool-approval-response',
      approval_id: approvalId,
      approved,
    });
    setRequests((prev) => prev.filter((r) => r.approval_id !== approvalId));
  }, []);

  const current = requests.length > 0 ? requests[0] : null;

  return { current, pendingCount: requests.length, respond };
}
