import dynamic from "next/dynamic";

const CustomerApp = dynamic(() => import("../../src/App"), { ssr: false });

export default function PaymentSuccess() {
  return <CustomerApp />;
}
