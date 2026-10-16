// Neon service configuration for NextGenTSofia Trade
// Provisioned with Lakebase Postgres on Neon (ap-southeast-1)
export const neonConfig = {
  orgId: "org-rough-wave-74341757",
  projectId: "damp-lake-44232884",
  branch: "production",
  services: {
    postgres: {
      envVar: "DATABASE_URL",
      unpooledEnvVar: "DATABASE_URL_UNPOOLED",
      database: "neondb",
      role: "neondb_owner",
      pooledHost: "ep-weathered-forest-aomnfoor-pooler.c-2.ap-southeast-1.aws.neon.tech",
    },
  },
};

export default neonConfig;
