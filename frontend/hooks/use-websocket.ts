'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketMessage {
  type: string;
  data: any;
  scan_id?: number;
  task_id?: string;
}

interface WebSocketHookOptions {
  url?: string;
  reconnect?: boolean;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export const useWebSocket = (options: WebSocketHookOptions = {}) => {
  const {
    url = 'ws://localhost:8000/ws',
    reconnect = true,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const messageListeners = useRef<Set<(message: WebSocketMessage) => void>>(new Set());

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnectionStatus('connecting');
    
    try {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectCount.current = 0;
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('[WebSocket] Message received:', message);
          
          setLastMessage(message);
          
          // Notify all listeners
          messageListeners.current.forEach(listener => {
            try {
              listener(message);
            } catch (error) {
              console.error('[WebSocket] Error in message listener:', error);
            }
          });
        } catch (error) {
          console.error('[WebSocket] Error parsing message:', error);
        }
      };

      ws.current.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setConnectionStatus('error');
      };

      ws.current.onclose = (event) => {
        console.log('[WebSocket] Disconnected:', event.code, event.reason);
        setIsConnected(false);
        setConnectionStatus('disconnected');
        ws.current = null;

        // Attempt reconnection
        if (reconnect && reconnectCount.current < reconnectAttempts) {
          reconnectCount.current++;
          console.log(`[WebSocket] Attempting to reconnect (${reconnectCount.current}/${reconnectAttempts})...`);
          
          setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      setConnectionStatus('error');
    }
  }, [url, reconnect, reconnectAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
    setIsConnected(false);
    setConnectionStatus('disconnected');
    reconnectCount.current = 0;
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      try {
        ws.current.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('[WebSocket] Error sending message:', error);
        return false;
      }
    } else {
      console.warn('[WebSocket] Not connected. Cannot send message.');
      return false;
    }
  }, []);

  // Subscribe to scan updates
  const subscribeTo = useCallback((scanId: number) => {
    sendMessage({
      type: 'subscribe_scan',
      scan_id: scanId
    });
  }, [sendMessage]);

  // Unsubscribe from scan updates
  const unsubscribeFrom = useCallback((scanId: number) => {
    sendMessage({
      type: 'unsubscribe_scan',
      scan_id: scanId
    });
  }, [sendMessage]);

  // Add message listener
  const addMessageListener = useCallback((listener: (message: WebSocketMessage) => void) => {
    messageListeners.current.add(listener);
    
    // Return cleanup function
    return () => {
      messageListeners.current.delete(listener);
    };
  }, []);

  // Initialize connection
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    connectionStatus,
    lastMessage,
    connect,
    disconnect,
    sendMessage,
    subscribeTo,
    unsubscribeFrom,
    addMessageListener,
  };
};

// Hook for monitoring specific scan progress
export const useScanProgress = (scanId: number | null) => {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [phase, setPhase] = useState('');
  
  const { isConnected, subscribeTo, unsubscribeFrom, addMessageListener } = useWebSocket();

  useEffect(() => {
    if (!scanId || !isConnected) return;

    // Subscribe to scan updates
    subscribeTo(scanId);

    // Add listener for this specific scan
    const removeListener = addMessageListener((message) => {
      if (message.type === 'scan_progress' && message.scan_id === scanId) {
        setProgress(message.data.progress || 0);
        setStatus(message.data.status || '');
        setPhase(message.data.current_phase || '');
      }
      
      if (message.type === 'scan_completed' && message.scan_id === scanId) {
        setProgress(100);
        setStatus('Completed');
        setPhase('Done');
      }
      
      if (message.type === 'scan_failed' && message.scan_id === scanId) {
        setProgress(0);
        setStatus('Failed');
        setPhase('Error');
      }
    });

    return () => {
      removeListener();
      unsubscribeFrom(scanId);
    };
  }, [scanId, isConnected, subscribeTo, unsubscribeFrom, addMessageListener]);

  return { progress, status, phase };
};