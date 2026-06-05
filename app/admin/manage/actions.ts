"use server";

import { isAdmin } from "@/lib/admin";
import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";

function guard() {
  if (!isAdmin()) redirect("/admin/login");
}

function s(formData: FormData, key: string) {
  return String(formData.get(key) || "").trim();
}

function id(formData: FormData) {
  return s(formData, "id");
}

function phone(formData: FormData) {
  return s(formData, "phone").replace(/[^0-9+]/g, "");
}

function dateOnly(formData: FormData, key: string) {
  return new Date(`${s(formData, key)}T00:00:00.000Z`);
}

function dateTime(formData: FormData, key: string) {
  return new Date(s(formData, key));
}

function price(formData: FormData) {
  const raw = s(formData, "finalPrice");
  return raw ? Number(raw) : null;
}

export async function createManualClient(formData: FormData) {
  guard();
  const status = s(formData, "status") || "APPROVED";
  await prisma.client.create({
    data: {
      firstName: s(formData, "firstName"),
      lastName: s(formData, "lastName"),
      phone: phone(formData),
      birthDate: dateOnly(formData, "birthDate"),
      status: status as any,
      notes: s(formData, "notes"),
      approvedAt: status === "APPROVED" ? new Date() : null,
      bannedAt: status === "BANNED" ? new Date() : null
    }
  });
  redirect("/admin/manage");
}

export async function updateManualClient(formData: FormData) {
  guard();
  const status = s(formData, "status") || "APPROVED";
  await prisma.client.update({
    where: { id: id(formData) },
    data: {
      firstName: s(formData, "firstName"),
      lastName: s(formData, "lastName"),
      phone: phone(formData),
      birthDate: dateOnly(formData, "birthDate"),
      status: status as any,
      notes: s(formData, "notes"),
      approvedAt: status === "APPROVED" ? new Date() : null,
      bannedAt: status === "BANNED" ? new Date() : null
    }
  });
  redirect("/admin/manage");
}

export async function createManualBooking(formData: FormData) {
  guard();
  const serviceId = s(formData, "serviceId");
  const service = await prisma.service.findUniqueOrThrow({ where: { id: serviceId } });
  const startAt = dateTime(formData, "startAt");
  const endAt = new Date(startAt.getTime() + service.durationMinutes * 60_000);
  const status = s(formData, "status") || "CONFIRMED";
  await prisma.booking.create({
    data: {
      clientId: s(formData, "clientId"),
      serviceId,
      startAt,
      endAt,
      status: status as any,
      clientComment: s(formData, "clientComment"),
      adminComment: s(formData, "adminComment"),
      finalPrice: price(formData),
      confirmedAt: status === "CONFIRMED" ? new Date() : null
    }
  });
  redirect("/admin/manage");
}

export async function updateManualBooking(formData: FormData) {
  guard();
  const serviceId = s(formData, "serviceId");
  const service = await prisma.service.findUniqueOrThrow({ where: { id: serviceId } });
  const startAt = dateTime(formData, "startAt");
  const endAt = new Date(startAt.getTime() + service.durationMinutes * 60_000);
  const status = s(formData, "status") || "CONFIRMED";
  await prisma.booking.update({
    where: { id: id(formData) },
    data: {
      clientId: s(formData, "clientId"),
      serviceId,
      startAt,
      endAt,
      status: status as any,
      clientComment: s(formData, "clientComment"),
      adminComment: s(formData, "adminComment"),
      finalPrice: price(formData),
      confirmedAt: status === "CONFIRMED" ? new Date() : undefined,
      cancelledAt: status.includes("CANCELLED") || status === "REJECTED" ? new Date() : undefined
    }
  });
  redirect("/admin/manage");
}

export async function cancelManualBooking(formData: FormData) {
  guard();
  await prisma.booking.update({
    where: { id: id(formData) },
    data: { status: "CANCELLED_BY_ADMIN", cancelledAt: new Date() }
  });
  redirect("/admin/manage");
}
