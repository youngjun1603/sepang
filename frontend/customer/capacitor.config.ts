import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "kr.sepang.customer",
  appName: "세팡",
  webDir: "out",
  server: {
    // 개발 시 로컬 Next.js 서버로 라우팅 (프로덕션에서는 제거)
    // url: "http://192.168.x.x:3000",
    // cleartext: true,
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: "#0057FF",
      androidSplashResourceName: "splash",
      showSpinner: false,
    },
    StatusBar: {
      style: "DARK",
      backgroundColor: "#0057FF",
    },
  },
  android: {
    buildOptions: {
      keystorePath: "release.keystore",
      keystoreAlias: "sepang-customer",
    },
  },
  ios: {
    contentInset: "always",
  },
};

export default config;
