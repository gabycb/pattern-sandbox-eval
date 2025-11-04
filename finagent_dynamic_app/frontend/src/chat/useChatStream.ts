import { useEffect, useMemo, useRef, useState } from 'react';
import { WebPubSubClient } from '@azure/web-pubsub-client';
import type { AgentMessage, ChatStatusResponse } from '../lib/api';

interface StreamOptions {
  taskId: string;
  sessionId: string;
  hubUrl?: string;
  group?: string;
}

interface StreamEvent {
  type: string;
  data: unknown;
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
    clientRef.current?.stop().catch(() => undefined);
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
        setConnectionError(null);
        await client.start();
        await client.joinGroup(group);
        setConnected(true);
      } catch (err) {
        console.error('Web PubSub connection failed', err);
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

    const messageHandler = (event: StreamEvent) => {
      if (typeof event?.data !== 'string') {
        return;
      }
      try {
        const parsed = JSON.parse(event.data);
        if (parsed?.type === 'message' && parsed?.data?.message) {
          setMessages(prev => {
            const already = prev.some(msg => msg.id === parsed.data.message.id);
            return already ? prev : [...prev, parsed.data.message];
          });
        } else if (parsed?.data?.plan) {
          setPlanPayload(parsed.data.plan);
        }
      } catch (error) {
        console.warn('Failed to parse chat stream payload', error);
      }
    };

    client.on('connected', connectedHandler);
    client.on('disconnected', reconnectHandler);
    client.on('group-message', messageHandler);

    connect();

    return () => {
      client.off('connected', connectedHandler);
      client.off('disconnected', reconnectHandler);
      client.off('group-message', messageHandler);
      client.stop().catch(() => undefined);
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
