import React, { useLayoutEffect, useMemo, useRef } from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import { InfiniteCanvas } from "./infinite-canvas";
import type { ViewportTransform } from "./types";

type CanvasNode = { id: string; x: number; y: number; w?: number; h?: number; type: string };
type Scene = { nodes: CanvasNode[]; viewport: ViewportTransform; tool: "select" | "pan"; epoch: number };
type LegacyBridge = {
    renderNode: (node: CanvasNode) => HTMLElement;
    nodeSize: (node: CanvasNode) => { w: number; h: number };
    keepMounted: (node: CanvasNode) => boolean;
    onViewportChange: (viewport: ViewportTransform) => void;
    onNodeMount: (node: CanvasNode, element: HTMLElement) => void;
    onNodeUnmount: (node: CanvasNode) => void;
    onNodeReplace: (node: CanvasNode, previous: HTMLElement, fresh: HTMLElement) => void;
};

declare global {
    interface Window {
        CanvasEngineBridge?: LegacyBridge;
        CanvasEngine?: {
            active: boolean;
            render: (nodes: CanvasNode[], viewport: ViewportTransform) => void;
            updateViewport: (viewport: ViewportTransform) => void;
            updateTool: (tool: "select" | "pan") => void;
            visibleIds: () => string[];
            clear: () => void;
        };
    }
}

const detachedNodes = new Map<string, { element: HTMLElement; epoch: number }>();
let currentVisibleIds: string[] = [];

function EngineNode({ node, epoch }: { node: CanvasNode; epoch: number }) {
    const host = useRef<HTMLSpanElement>(null);
    useLayoutEffect(() => {
        const bridge = window.CanvasEngineBridge;
        const root = host.current;
        if (!bridge || !root) return;
        const cached = detachedNodes.get(node.id);
        detachedNodes.delete(node.id);
        const element = cached?.epoch === epoch ? cached.element : bridge.renderNode(node);
        if (cached && cached.element !== element) {
            bridge.onNodeReplace(node, cached.element, element);
            cached.element.remove();
        }
        root.appendChild(element);
        bridge.onNodeMount(node, element);
        return () => {
            const current = root.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(node.id)}"]`) || element;
            const preserve = bridge.keepMounted(node);
            bridge.onNodeUnmount(node);
            if (preserve) detachedNodes.set(node.id, { element: current, epoch });
            current.remove();
        };
    }, [node, epoch]);
    return <span ref={host} className="canvas-engine-node-host" data-id={node.id} />;
}

function EngineApp({ scene }: { scene: Scene }) {
    const containerRef = useRef<HTMLDivElement>(null);
    const visibleNodes = useMemo(() => {
        // Same viewport test as upstream canvas-client-page.tsx at f30b8d7.
        const padding = 280;
        const rect = containerRef.current?.getBoundingClientRect();
        const width = rect?.width || window.innerWidth;
        const height = rect?.height || window.innerHeight;
        const viewLeft = -scene.viewport.x / scene.viewport.k - padding;
        const viewTop = -scene.viewport.y / scene.viewport.k - padding;
        const viewRight = viewLeft + width / scene.viewport.k + padding * 2;
        const viewBottom = viewTop + height / scene.viewport.k + padding * 2;
        const bridge = window.CanvasEngineBridge;
        return scene.nodes.filter((node) => {
            if (bridge?.keepMounted(node)) return true;
            const size = bridge?.nodeSize(node) || { w: node.w || 260, h: node.h || 160 };
            return node.x + size.w > viewLeft && node.x < viewRight && node.y + size.h > viewTop && node.y < viewBottom;
        });
    }, [scene.nodes, scene.viewport]);
    currentVisibleIds = visibleNodes.map((node) => node.id);

    return <InfiniteCanvas
        containerRef={containerRef}
        viewport={scene.viewport}
        tool={scene.tool}
        backgroundMode="blank"
        onViewportChange={(next) => window.CanvasEngineBridge?.onViewportChange(next)}
    >
        <svg id="links" className="links" />
        <div id="linkControls" className="link-controls" />
        <div id="nodes">{visibleNodes.map((node) => <EngineNode key={node.id} node={node} epoch={scene.epoch} />)}</div>
    </InfiniteCanvas>;
}

const mount = document.getElementById("canvasEngineRoot");
if (mount && !mount.hidden) {
    const root = createRoot(mount);
    let scene: Scene = { nodes: [], viewport: { x: 0, y: 0, k: 1 }, tool: "select", epoch: 0 };
    const draw = () => flushSync(() => root.render(<EngineApp scene={scene} />));
    draw();
    window.CanvasEngine = {
        active: true,
        render(nodes, viewport) {
            scene = { nodes: nodes.slice(), viewport: { ...viewport }, epoch: scene.epoch + 1 };
            draw();
        },
        updateViewport(viewport) {
            scene = { ...scene, viewport: { ...viewport } };
            draw();
        },
        updateTool(tool) {
            scene = { ...scene, tool };
            draw();
        },
        visibleIds() { return currentVisibleIds.slice(); },
        clear() {
            scene = { ...scene, nodes: [], epoch: scene.epoch + 1 };
            draw();
            detachedNodes.clear();
        },
    };
}
