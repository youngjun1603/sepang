import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "kr.sepang.partner",
  appName: "세팡 파트너",
  webDir: "out",
  server: {
    // 개발 시 로컬 Next.js 서버로 라우팅 (프로덕션에서는 제거)
    // url: "http://192.168.x.x:3001",
    // cleartext: true,
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: "#FFD600",
      androidSplashResourceName: "splash",
      showSpinner: false,
    },
    StatusBar: {
      style: "LIGHT",
      backgroundColor: "#FFD600",
    },
    Geolocation: {
      // 파트너 위치 기반 주문 배정용
    },
  },
  android: {
    buildOptions: {
      keystorePath: "release.keystore",
      keystoreAlias: "sepang-partner",
    },
  },
  ios: {
    contentInset: "always",
  },
};

export default config;
