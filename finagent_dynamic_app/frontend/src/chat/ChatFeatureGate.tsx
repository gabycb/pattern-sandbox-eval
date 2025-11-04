import { PropsWithChildren } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../lib/api';

export function ChatFeatureGate({ children }: PropsWithChildren) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['chat', 'config'],
    queryFn: () => apiClient.getChatConfig(),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading || isError) {
    return null;
  }

  if (!data?.enabled) {
    return null;
  }

  return <>{children}</>;
}
