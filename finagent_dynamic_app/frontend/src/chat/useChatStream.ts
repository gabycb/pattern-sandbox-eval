import { useEffect, useMemo, useRef, useState } from 'react';
import { WebPubSubClient } from '@azure/web-pubsub-client';
import type { AgentMessage, ChatStatusResponse } from '../lib/api';

interface StreamOptions {
  taskId: string;
  sessionId: string;
  hubUrl?: string;
  group?: string;
}

export function useChatStream({ taskId, sessionId, hubUrl, group }: StreamOptions) {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [planPayload, setPlanPayload] = useState<ChatStatusResponse['plan'] | null>(null);
  const [connected, setConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const clientRef = useRef<InstanceType<typeof WebPubSubClient> | null>(null);

  useEffect(() => {
    setMessages([]);
    setPlanPayload(null);
    setConnectionError(null);
    setConnected(false);
    clientRef.current?.stop()?.catch(() => undefined);
    clientRef.current = null;
  }, [taskId, sessionId]);

  useEffect(() => {
    if (!hubUrl || !group) {
      return;
    }

    const client = new WebPubSubClient({
      getClientAccessUrl: async () => hubUrl,
      autoNegotiation: false,
    });

  clientRef.current = client;

    const connect = async () => {
      try {
        console.log('=== WebPubSub Connect Attempt ===');
        console.log('Hub URL:', hubUrl);
        console.log('Group:', group);
        setConnectionError(null);
        await client.start();
        console.log('✓ WebPubSub client started');
        await client.joinGroup(group);
        console.log('✓ Joined group:', group);
        setConnected(true);
      } catch (err) {
        console.error('✗ Web PubSub connection failed', err);
        setConnectionError('Realtime connection unavailable');
        setConnected(false);
      }
    };

    const reconnectHandler = () => {
      setConnected(false);
    };

    const connectedHandler = () => {
      setConnected(true);
    };

    const messageHandler = (event: any) => {
      console.log('=== group-message received ===', event);
      
      // Azure Web PubSub sends data in event.message.data, not event.data
      const messageData = event?.message?.data || event?.data;
      console.log('Message data:', messageData);
      console.log('Message data type:', typeof messageData);
      
      if (typeof messageData !== 'string') {
        console.warn('Message data is not a string:', typeof messageData, messageData);
        return;
      }
      try {
        const parsed = JSON.parse(messageData);
        console.log('Parsed message:', parsed);
        if (parsed?.type === 'message' && parsed?.data?.message) {
          console.log('→ Adding message to state');
          setMessages(prev => {
            const already = prev.some(msg => msg.id === parsed.data.message.id);
            return already ? prev : [...prev, parsed.data.message];
          });
        } else if (parsed?.data?.plan) {
          console.log('→ Updating plan payload');
          setPlanPayload(parsed.data.plan);
        }
      } catch (error) {
        console.warn('Failed to parse chat stream payload', error);
      }
    };

    // Add debug handler for all event types
    const debugHandler = (event: any) => {
      console.log('=== WebPubSub ANY event ===', event?.type || 'unknown', event);
    };

    client.on('connected', connectedHandler);
    client.on('disconnected', reconnectHandler);
    client.on('group-message', messageHandler);
    client.on('server-message', debugHandler);
    client.on('message', debugHandler);

    connect();

    return () => {
      client.off('connected', connectedHandler);
      client.off('disconnected', reconnectHandler);
      client.off('group-message', messageHandler);
      client.off('server-message', debugHandler);
      client.off('message', debugHandler);
      client.stop()?.catch(() => undefined);
      clientRef.current = null;
    };
  }, [hubUrl, group]);

  const state = useMemo(
    () => ({
      taskId,
      sessionId,
      plan: planPayload,
      messages,
      connected,
      connectionError,
    }),
    [taskId, sessionId, planPayload, messages, connected, connectionError]
  );

  return state;
}
