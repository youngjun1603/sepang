import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="ko">
      <Head>
        {/* PWA 기본 설정 */}
        <meta name="application-name" content="세팡" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="세팡" />
        <meta name="description" content="12시간 이내 수거·세탁·배송 완료" />
        <meta name="format-detection" content="telephone=no" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="theme-color" content="#0057FF" />

        {/* PWA Manifest */}
        <link rel="manifest" href="/manifest.json" />

        {/* Apple Touch Icons */}
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
        <link rel="apple-touch-icon" sizes="152x152" href="/icons/icon-152.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png" />
        <link rel="apple-touch-icon" sizes="167x167" href="/icons/icon-167.png" />

        {/* iOS 스플래시 스크린 */}
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />

        {/* Favicon */}
        <link rel="icon" type="image/svg+xml" href="/icons/icon.svg" />
        <link rel="shortcut icon" href="/icons/favicon.ico" />

        {/* OG 태그 */}
        <meta property="og:type" content="website" />
        <meta property="og:title" content="세팡 — 당일 세탁 서비스" />
        <meta property="og:description" content="12시간 이내 수거·세탁·배송 완료" />
        <meta property="og:site_name" content="세팡" />
        <meta property="og:url" content="https://sepang.kr" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
