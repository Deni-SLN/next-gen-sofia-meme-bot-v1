import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="id" className="dark">
      <Head>
        <link rel="manifest" href="/manifest.json" />
        <link rel="icon" href="/icon-192.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/icon-192.svg" />
        <meta name="theme-color" content="#10b981" />
        <meta name="application-name" content="Sofia Market 4.0" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="Sofia 4.0" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta
          name="description"
          content="Sofia Market 4.0 (SFIA 4.0) — Multi-Asset Quantitative Terminal & Autonomous Meme Coin Sniper."
        />
      </Head>
      <body className="bg-obsidian-950 text-slate-200 antialiased">
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
