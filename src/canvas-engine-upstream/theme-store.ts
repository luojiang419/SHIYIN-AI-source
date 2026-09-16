export function useThemeStore<T>(selector: (state: { theme: "light" }) => T): T {
    return selector({ theme: "light" });
}
