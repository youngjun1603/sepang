import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="ko">
      <Head>
        <meta name="application-name" content="세팡 어드민" />
        <meta name="description" content="세팡 운영 관리 대시보드" />
        <meta name="robots" content="noindex, nofollow" />
        <meta name="theme-color" content="#1E1E2E" />

        {/* Favicon */}
        <link rel="icon" type="image/svg+xml" href="/icons/icon.svg" />
        <link rel="shortcut icon" href="/icons/favicon.ico" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
