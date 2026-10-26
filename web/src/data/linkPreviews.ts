import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { call } from "./request";

/** The site's title, description and image as the API read them; a site that did not answer has only the domain. */
export function useLinkPreview(url: string) {
  return useQuery({
    queryKey: ["link-preview", url],
    queryFn: () => call(api.GET("/v1/link-preview", { params: { query: { url } } })),
    // A site's card rarely changes while a page is open; asking again would fetch the site again.
    staleTime: 60 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
