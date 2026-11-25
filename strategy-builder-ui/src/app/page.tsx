import { redirect } from "next/navigation";

// `/tos` is the only screen this app serves (legacy removal L5). The root stays
// a route rather than a 404 for two concrete callers: the container healthcheck
// in docker-compose.yml (`fetch('http://localhost:3100/')`, which follows the
// redirect and so still reports healthy) and scripts/deploy_paper.sh, which
// probes the host root through Caddy.
export default function RootPage() {
  redirect("/tos");
}
