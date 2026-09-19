import React, { useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import { InfiniteCanvas } from "./infinite-canvas";
import type { ViewportTransform } from "./types";

type CanvasNode = { id: string; x: number; y: number; w?: number; h?: number; type: string };
type Scene = { nodes: CanvasNode[]; viewport: ViewportTransform; tool: "select" | "pan"; panButton: "primary" | "middle"; epoch: number };
type NodeBridge = {
    renderNode: (node: CanvasNode) => HTMLElement;
    nodeSize: (node: CanvasNode) => { w: number; h: number };
    keepMounted: (node: CanvasNode) => boolean;
    cacheDetached: (node: CanvasNode) => boolean;
    onViewportChange: (viewport: ViewportTransform) => void;
    onNodeMount: (node: CanvasNode, element: HTMLElement) => void;
    onNodeUnmount: (node: CanvasNode) => void;
    onNodeReplace: (node: CanvasNode, previous: HTMLElement, fresh: HTMLElement) => void;
    nodeRevision: (node: CanvasNode) => string;
    onNodeDispose: (node: CanvasNode, element: HTMLElement) => void;
    syncNode: (node: CanvasNode, element: HTMLElement) => void;
};

declare global {
    interface Window {
        CanvasEngineBridge?: NodeBridge;
        CanvasEngine?: {
            active: boolean;
            render: (nodes: CanvasNode[], viewport: ViewportTransform) => void;
            updateViewport: (viewport: ViewportTransform) => void;
            updateTool: (tool: "select" | "pan") => void;
            updatePanButton: (button: "primary" | "middle") => void;
            visibleIds: () => string[];
            clear: () => void;
            invalidate: (ids: string[]) => void;
            stats: () => { cached: number; mounted: number };
        };
    }
}

type NodeRecord = { node: CanvasNode; element: HTMLElement; revision: string; mounted: boolean };
const records = new Map<string, NodeRecord>();
const invalidated = new Set<string>();
// 仅限制离屏 DOM 缓存，活动节点不淘汰。媒体不再叠加第二套驻留控制器。
const detachedLimit = 192;
function disposeRecord(id: string) {
    const record = records.get(id);
    if (!record) return;
    window.CanvasEngineBridge?.onNodeDispose(record.node, record.element);
    record.element.remove();
    records.delete(id);
}
function pruneRecords(ids: Set<string>) {
    let detached = [...records.values()].filter(record => !record.mounted).length;
    for (const [id, record] of records) {
        if (!record.mounted && (!ids.has(id) || detached > detachedLimit)) {
            disposeRecord(id);
            detached--;
        }
    }
}
let currentVisibleIds: string[] = [];

const EngineNode = React.memo(function EngineNode({ node, epoch }: { node: CanvasNode; epoch: number }) {
    const host = useRef<HTMLSpanElement>(null);
    useLayoutEffect(() => {
        const bridge = window.CanvasEngineBridge;
        const root = host.current;
        if (!bridge || !root) return;
        const cached = records.get(node.id);
        const revision = bridge.nodeRevision(node);
        const reuse = cached && cached.node === node && cached.revision === revision && !invalidated.has(node.id);
        const element = reuse ? cached.element : bridge.renderNode(node);
        if (cached && !reuse) {
            bridge.onNodeReplace(node, cached.element, element);
            bridge.onNodeDispose(cached.node, cached.element);
            cached.element.remove();
        }
        invalidated.delete(node.id);
        records.delete(node.id);
        records.set(node.id, { node, element, revision: bridge.nodeRevision(node), mounted: true });
        root.appendChild(element);
        bridge.syncNode(node, element);
        bridge.onNodeMount(node, element);
        return () => {
            const current = root.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(node.id)}"]`) || element;
            bridge.onNodeUnmount(node);
            const record = records.get(node.id);
            if (record) { record.element = current; record.mounted = false; }
            current.remove();
            if (!bridge.cacheDetached(node)) disposeRecord(node.id);
        };
    }, [node, epoch]);
    return <span ref={host} className="canvas-engine-node-host" data-id={node.id} />;
});

function EngineApp({ scene }: { scene: Scene }) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [size, setSize] = useState({ width: 0, height: 0 });
    useLayoutEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        const observer = new ResizeObserver(([entry]) => {
            const { width, height } = entry.contentRect;
            setSize(previous => previous.width === width && previous.height === height ? previous : { width, height });
        });
        observer.observe(container);
        return () => observer.disconnect();
    }, []);
    const visibleNodes = useMemo(() => {
        // Same viewport test as upstream canvas-client-page.tsx at f30b8d7.
        const padding = 280;
        const width = size.width || window.innerWidth;
        const height = size.height || window.innerHeight;
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
    }, [scene.nodes, scene.viewport, size]);
    currentVisibleIds = visibleNodes.map((node) => node.id);
    useLayoutEffect(() => { pruneRecords(new Set(scene.nodes.map(node => node.id))); });

    return <InfiniteCanvas
        containerRef={containerRef}
        viewport={scene.viewport}
        tool={scene.tool}
        panButton={scene.panButton}
        backgroundMode="blank"
        onViewportChange={(next) => window.CanvasEngineBridge?.onViewportChange(next)}
    >
        <svg id="links" className="links" />
        <div id="linkControls" className="link-controls" />
        <div id="nodes">{visibleNodes.map((node) => <EngineNode key={node.id} node={node} epoch={nodeVersions.get(node.id) || 0} />)}</div>
    </InfiniteCanvas>;
}

const mount = document.getElementById("canvasEngineRoot");
const nodeVersions = new Map<string, number>();
if (mount && !mount.hidden) {
    const root = createRoot(mount);
    let scene: Scene = { nodes: [], viewport: { x: 0, y: 0, k: 1 }, tool: "select", panButton: "middle", epoch: 0 };
    const draw = () => flushSync(() => root.render(<EngineApp scene={scene} />));
    draw();
    window.CanvasEngine = {
        active: true,
        render(nodes, viewport) {
            for (const node of nodes) {
                const record = records.get(node.id);
                if (!record || record.node !== node || record.revision !== window.CanvasEngineBridge?.nodeRevision(node) || invalidated.has(node.id)) {
                    nodeVersions.set(node.id, (nodeVersions.get(node.id) || 0) + 1);
                } else window.CanvasEngineBridge?.syncNode(node, record.element);
            }
            const ids = new Set(nodes.map(node => node.id));
            for (const id of nodeVersions.keys()) if (!ids.has(id)) nodeVersions.delete(id);
            for (const id of invalidated) if (!ids.has(id)) invalidated.delete(id);
            scene = { nodes: nodes.slice(), viewport: { ...viewport }, epoch: scene.epoch + 1 };
            draw();
        },
        updateViewport(viewport) {
            if (scene.viewport.x === viewport.x && scene.viewport.y === viewport.y && scene.viewport.k === viewport.k) return;
            scene = { ...scene, viewport: { ...viewport } };
            draw();
        },
        updateTool(tool) {
            scene = { ...scene, tool };
            draw();
        },
        updatePanButton(panButton) {
            scene = { ...scene, panButton };
            draw();
        },
        visibleIds() { return currentVisibleIds.slice(); },
        invalidate(ids) { ids.forEach(id => invalidated.add(id)); },
        stats() { return { cached: records.size, mounted: currentVisibleIds.length }; },
        clear() {
            scene = { ...scene, nodes: [], epoch: scene.epoch + 1 };
            draw();
            for (const id of records.keys()) disposeRecord(id);
            nodeVersions.clear();
            invalidated.clear();
        },
    };
}
