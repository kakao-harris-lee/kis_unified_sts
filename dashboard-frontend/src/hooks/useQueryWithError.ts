import { useQuery, UseQueryOptions, UseQueryResult } from '@tanstack/react-query';
import { AxiosError } from 'axios';

/**
 * Extract a user-friendly error message from an error object
 */
function getErrorMessage(error: unknown): string {
  if (!error) {
    return 'An unknown error occurred';
  }

  // Handle Axios errors
  if (error instanceof AxiosError) {
    // Try to get message from response data
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    // Use status text for HTTP errors
    if (error.response?.statusText) {
      return `${error.response.status}: ${error.response.statusText}`;
    }
    // Network errors
    if (error.message === 'Network Error') {
      return 'Unable to connect to server. Please check your connection.';
    }
    // Timeout errors
    if (error.code === 'ECONNABORTED') {
      return 'Request timeout. Please try again.';
    }
    // Default axios error message
    if (error.message) {
      return error.message;
    }
  }

  // Handle standard Error objects
  if (error instanceof Error) {
    return error.message;
  }

  // Handle string errors
  if (typeof error === 'string') {
    return error;
  }

  // Fallback
  return 'An unexpected error occurred';
}

export type UseQueryWithErrorResult<TData> = UseQueryResult<TData> & {
  errorMessage: string | null;
};

/**
 * Custom hook that wraps useQuery with standardized error handling
 *
 * @example
 * const { data, isLoading, errorMessage, refetch } = useQueryWithError({
 *   queryKey: ['trading-status'],
 *   queryFn: () => tradingApi.getStatus().then(r => r.data),
 * });
 *
 * // Display errors with ErrorMessage component
 * {errorMessage && <ErrorMessage message={errorMessage} onRetry={() => refetch()} />}
 */
export function useQueryWithError<
  TQueryFnData = unknown,
  TError = Error,
  TData = TQueryFnData,
  TQueryKey extends readonly unknown[] = readonly unknown[]
>(
  options: UseQueryOptions<TQueryFnData, TError, TData, TQueryKey>
): UseQueryWithErrorResult<TData> {
  const queryResult = useQuery(options);

  const errorMessage = queryResult.error
    ? getErrorMessage(queryResult.error)
    : null;

  return {
    ...queryResult,
    errorMessage,
  } as UseQueryWithErrorResult<TData>;
}

export default useQueryWithError;
