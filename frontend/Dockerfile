FROM node:20-alpine

WORKDIR /app

# Install dependencies in a separate layer for better cache re-use.
# package-lock.json* — the asterisk makes it optional so the COPY doesn't
# fail if the file is absent (though it should always exist for a locked install).
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# Copy source. In docker-compose development mode this layer is shadowed
# by the bind-mount volume, so edits on the host trigger Vite HMR instantly.
COPY . .

EXPOSE 5173

# Production default. docker-compose overrides this with -- --host.
CMD ["npm", "run", "dev"]
