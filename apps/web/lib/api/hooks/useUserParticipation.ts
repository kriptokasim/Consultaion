import { useQuery } from '@tanstack/react-query';
import { getUserParticipation } from '../../apiClient';

export function useUserParticipation() {
  return useQuery({
    queryKey: ['user', 'participation'],
    queryFn: getUserParticipation,
  });
}
