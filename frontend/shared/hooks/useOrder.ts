/**
 * useOrder — 주문 상태 관리 훅 (WebSocket 실시간 추적 포함)
 */
"use client";
import { useState, useEffect, useCallback } from "react";
import { orderApi, createOrderTrackingSocket, type Order, type OrderStatus } from "../lib/api-client";

// 주문 목록
export function useOrders() {
  const [orders,    setOrders]    = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error,     setError]     = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await orderApi.list();
      setOrders(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { orders, isLoading, error, refetch: fetch };
}

// 단일 주문 실시간 추적
export function useOrderTracking(orderId: string) {
  const [order,     setOrder]     = useState<Order | null>(null);
  const [status,    setStatus]    = useState<OrderStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) return;
    let ws: WebSocket;

    // 초기 데이터 로드
    orderApi.get(orderId).then(setOrder).catch((e) => setError(e.message));

    // WebSocket 연결
    ws = createOrderTrackingSocket(orderId, {
      onConnected: () => setConnected(true),
      onStatus:    (s) => { setStatus(s); setOrder((prev) => prev ? { ...prev, status: s } : null); },
      onError:     () => setError("실시간 연결이 끊어졌습니다"),
    });

    return () => { ws?.close(); };
  }, [orderId]);

  // SLA 카운트다운
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  useEffect(() => {
    if (!order?.deadline_at) return;
    const calc = () => {
      const left = Math.max(0, (new Date(order.deadline_at).getTime() - Date.now()) / 1000);
      setSecondsLeft(Math.floor(left));
    };
    calc();
    const iv = setInterval(calc, 1000);
    return () => clearInterval(iv);
  }, [order?.deadline_at]);

  const timeLeft = {
    hours:   Math.floor(secondsLeft / 3600),
    minutes: Math.floor((secondsLeft % 3600) / 60),
    seconds: secondsLeft % 60,
    display: [
      Math.floor(secondsLeft / 3600),
      Math.floor((secondsLeft % 3600) / 60),
      secondsLeft % 60,
    ].map((n) => String(n).padStart(2, "0")).join(":"),
    isUrgent:  secondsLeft < 7200,   // 2시간
    isDanger:  secondsLeft < 3600,   // 1시간
    isExpired: secondsLeft === 0,
  };

  return { order, status: status ?? order?.status, connected, error, timeLeft };
}

// 점주 — 인근 주문
export function useNearbyOrders(pollingMs = 30_000) {
  const [orders,    setOrders]    = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const data = await orderApi.nearbyOrders();
      setOrders(data);
    } catch { /* silent */ }
    finally { setIsLoading(false); }
  }, []);

  useEffect(() => {
    fetch();
    const iv = setInterval(fetch, pollingMs);
    return () => clearInterval(iv);
  }, [fetch, pollingMs]);

  const acceptOrder = useCallback(async (orderId: string) => {
    await orderApi.updateStatus(orderId, "ACCEPTED");
    await fetch();
  }, [fetch]);

  const updateStatus = useCallback(async (orderId: string, status: OrderStatus, note?: string) => {
    await orderApi.updateStatus(orderId, status, note);
    await fetch();
  }, [fetch]);

  return { orders, isLoading, acceptOrder, updateStatus, refetch: fetch };
}

// 점주 — 사진 업로드
export function usePhotoUpload(orderId: string) {
  const [uploading, setUploading] = useState<Record<string, boolean>>({});
  const [uploaded,  setUploaded]  = useState<Record<string, string>>({});   // type → view_url
  const [error,     setError]     = useState<string | null>(null);

  const upload = useCallback(async (type: "PICKUP"|"DELIVERY"|"ISSUE", file: File) => {
    setUploading((p) => ({ ...p, [type]: true }));
    setError(null);
    try {
      const result = await orderApi.uploadPhoto(orderId, type, file);
      setUploaded((p) => ({ ...p, [type]: result.view_url }));
      return result;
    } catch (e: any) {
      setError(e.message);
      throw e;
    } finally {
      setUploading((p) => ({ ...p, [type]: false }));
    }
  }, [orderId]);

  return { upload, uploading, uploaded, error };
}
