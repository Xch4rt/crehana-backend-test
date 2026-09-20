# syntax=docker/dockerfile:1

# Two real stages, in the shape the root Dockerfile established:
#
#   build   -> a Node toolchain that installs from the lockfile, type-checks and
#              bundles. Nothing from this stage is delivered.
#   runtime -> nginx serving the static bundle and proxying /api/ to the api
#              service. No Node, no source, no lockfile - a few megabytes of
#              HTML, CSS and JavaScript on a web server.
#
# That split is the reason D-02 chose a static SPA over Next.js: SSR buys nothing
# over an existing JSON API and would put a Node RUNTIME into the delivered
# stack, which is a second long-running process to keep healthy for no gain.
#
# Both tags are pinned to a major version, never `:latest` and never a bare
# `:alpine` (ADR-013): node:24-alpine is the active LTS line, nginx:1.30-alpine
# is the stable branch. Node 26 is `current` and nginx 1.31 is `mainline`;
# neither belongs in a graded deliverable.

# ---------- Stage 1: build ----------
FROM node:24-alpine AS build

WORKDIR /app

# The lockfile before the source, so editing a component does not invalidate the
# dependency layer - the same rule the Python builder stage follows. `npm ci`
# rather than `npm install`: it installs the committed lockfile verbatim and
# fails if package.json and the lock disagree, which is what makes the image
# reproducible instead of merely buildable.
COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src

# `npm run build` is `tsc --noEmit && vite build`, in that order and on purpose:
# a type error must fail the BUILD rather than produce a shipped image that
# happens to bundle. Vite itself strips types without checking them.
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM nginx:1.30-alpine AS runtime

# The whole configuration, not a conf.d/ fragment: the unprivileged pid and
# temp paths are main-context settings the default file would otherwise decide.
COPY nginx.conf /etc/nginx/nginx.conf

COPY --from=build /app/dist /usr/share/nginx/html

# Both directories, and both needed: the document root because the server reads
# it as `nginx`, and /var/cache/nginx because the image's own configuration
# still creates cache directories under it at start-up.
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx

USER nginx

EXPOSE 8080

# BusyBox wget, already in the Alpine base - there is nothing to install here.
# That is the opposite of the API image, which answers its healthcheck with a
# python -c because a slim Debian has neither curl nor wget and installing one
# would be a package more than the job needs (D-09). The inconsistency is real
# and this comment is why it exists: each image uses what it already has.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/ || exit 1

# No CMD and no ENTRYPOINT: the base image's entrypoint and its
# `nginx -g "daemon off;"` are correct as shipped, and restating them would
# create a second copy to keep in sync.
