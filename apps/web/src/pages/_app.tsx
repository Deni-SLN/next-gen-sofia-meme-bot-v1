import React, { useEffect } from 'react';
import type { AppProps } from 'next/app';
import Head from 'next/head';
import { Layout } from '@/components/Layout';
import '@/styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  useEffect(() => {
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  }, []);

  return (
    <>
      <Head>
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover"
        />
        <title>SOFIA Trenches v3.8 PRO — Meme Coin Sniper &amp; AI Trading</title>
      </Head>
      <Layout>
        <Component {...pageProps} />
      </Layout>
    </>
  );
}
