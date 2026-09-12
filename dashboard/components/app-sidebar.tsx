"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Chrome, KeyRound, LogOut } from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { BrowserLogo } from "@/components/browser-logo"
import { logout, type User } from "@/lib/auth"

const NAV = [
  { href: "/", label: "Browsers", icon: Chrome },
  { href: "/keys", label: "API Keys", icon: KeyRound },
]

export function AppSidebar({ user }: { user: User }) {
  const pathname = usePathname()
  const router = useRouter()

  async function handleLogout() {
    try {
      await logout()
    } catch {
      /* ignore */
    }
    router.replace("/login")
  }

  return (
    <Sidebar collapsible="icon" className="border-r-2 border-border">
      <SidebarHeader className="border-b-2 border-border bg-secondary-background">
        <div className="group-data-[collapsible=icon]:justify-center flex items-center gap-2.5 px-3 py-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-base border-2 border-border bg-main text-main-foreground shadow-shadow">
            <BrowserLogo className="h-6 w-6" />
          </span>
          <span className="sidebar-text flex flex-col leading-tight">
            <span className="text-[15px] font-bold font-heading">BrowserMesh</span>
            <span className="text-[11px] text-muted-foreground">headless browsers</span>
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-2 pt-2">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="gap-2">
              {NAV.map(({ href, label, icon: Icon }) => {
                const active = pathname === href
                return (
                  <SidebarMenuItem key={href}>
                    <SidebarMenuButton asChild size="lg" isActive={active} tooltip={label}>
                      <Link
                        href={href}
                        className="h-auto min-h-11 justify-start gap-3 rounded-base border-2 border-border bg-background px-3 py-2 text-left shadow-shadow data-[active=true]:translate-x-boxShadowX data-[active=true]:translate-y-boxShadowY data-[active=true]:shadow-none"
                      >
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-base border-2 border-border bg-secondary-background">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="sidebar-text text-sm font-bold font-heading">{label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t-2 border-border bg-secondary-background">
        <div className="flex flex-col gap-2 p-3">
          <div className="flex items-center gap-2 rounded-base border-2 border-border bg-background px-3 py-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-green-500" />
            <span className="sidebar-text truncate text-xs text-foreground/70">{user.email}</span>
          </div>
          <Button variant="neutral" className="w-full justify-center shadow-shadow" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            <span className="sidebar-text">Sign out</span>
          </Button>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
