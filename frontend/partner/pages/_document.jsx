import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="ko">
      <Head>
        {/* PWA 기본 설정 */}
        <meta name="application-name" content="세팡 파트너" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="세팡 파트너" />
        <meta name="description" content="세팡 파트너 — 주문 접수·처리 앱" />
        <meta name="format-detection" content="telephone=no" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="theme-color" content="#FFD600" />

        {/* PWA Manifest */}
        <link rel="manifest" href="/manifest.json" />

        {/* Apple Touch Icons */}
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <link rel="apple-touch-icon" sizes="152x152" href="/icons/icon-152.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png" />
        <link rel="apple-touch-icon" sizes="167x167" href="/icons/icon-167.png" />

        {/* Favicon */}
        <link rel="icon" type="image/svg+xml" href="/icons/icon.svg" />
        <link rel="shortcut icon" href="/icons/favicon.ico" />

        {/* OG 태그 */}
        <meta property="og:type" content="website" />
        <meta property="og:title" content="세팡 파트너" />
        <meta property="og:description" content="세팡 파트너 — 주문 접수·처리 앱" />
        <meta property="og:site_name" content="세팡 파트너" />
        <meta property="og:url" content="https://partner.sepang.kr" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
