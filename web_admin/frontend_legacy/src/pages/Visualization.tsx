import { useState, useRef } from 'react';
import { useAppStore } from '@/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Share2,
  Plus,
  Minus,
  Maximize,
  Trash2,
  GitBranch,
  MessageCircle,
  ArrowRight,
  MousePointer2,
} from 'lucide-react';
import type { GraphNode, GraphEdge } from '@/types';

// Mock graph data
const mockNodes: GraphNode[] = [
  { id: 'chat1', type: 'chat', label: '新闻源频道', data: { telegram_chat_id: '-1001234567890' }, x: 100, y: 100 },
  { id: 'chat2', type: 'chat', label: '技术讨论组', data: { telegram_chat_id: '-1002345678901' }, x: 100, y: 250 },
  { id: 'chat3', type: 'chat', label: '监控告警', data: { telegram_chat_id: '-1003456789012' }, x: 100, y: 400 },
  { id: 'rule1', type: 'rule', label: '规则 #1', data: { enabled: true, keywords_count: 5 }, x: 400, y: 100 },
  { id: 'rule2', type: 'rule', label: '规则 #2', data: { enabled: true, keywords_count: 3 }, x: 400, y: 250 },
  { id: 'rule3', type: 'rule', label: '规则 #3', data: { enabled: false, keywords_count: 8 }, x: 400, y: 400 },
  { id: 'target1', type: 'chat', label: '聚合推送群', data: { telegram_chat_id: '-1009876543210' }, x: 700, y: 175 },
  { id: 'target2', type: 'chat', label: '值班群', data: { telegram_chat_id: '-1008765432109' }, x: 700, y: 325 },
];

const mockEdges: GraphEdge[] = [
  { source: 'chat1', target: 'rule1', type: 'default' },
  { source: 'chat2', target: 'rule2', type: 'default' },
  { source: 'chat3', target: 'rule3', type: 'default' },
  { source: 'rule1', target: 'target1', type: 'default' },
  { source: 'rule2', target: 'target1', type: 'default' },
  { source: 'rule2', target: 'target2', type: 'default' },
  { source: 'rule3', target: 'target2', type: 'default' },
];

export function Visualization() {
  const { addNotification } = useAppStore();
  const [nodes, setNodes] = useState<GraphNode[]>(mockNodes);
  const [edges] = useState<GraphEdge[]>(mockEdges);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [connectionMode, setConnectionMode] = useState(false);
  const [connectionFrom, setConnectionFrom] = useState<string | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale((s) => Math.max(0.5, Math.min(2, s * delta)));
  };

  const handleMouseDown = (e: React.MouseEvent, nodeId?: string) => {
    if (nodeId) {
      if (connectionMode) {
        if (!connectionFrom) {
          setConnectionFrom(nodeId);
          addNotification({ message: '请选择目标节点', type: 'info' });
        } else if (connectionFrom !== nodeId) {
          addNotification({ message: '已创建连接', type: 'success' });
          setConnectionFrom(null);
          setConnectionMode(false);
        }
        return;
      }
      setIsDragging(true);
      setDraggedNode(nodeId);
      if (e.ctrlKey || e.metaKey) {
        setSelectedNodes((prev) => {
          const next = new Set(prev);
          if (next.has(nodeId)) {
            next.delete(nodeId);
          } else {
            next.add(nodeId);
          }
          return next;
        });
      } else {
        setSelectedNodes(new Set([nodeId]));
      }
    } else {
      setIsDragging(true);
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    
    if (draggedNode) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      
      const x = (e.clientX - rect.left - pan.x) / scale;
      const y = (e.clientY - rect.top - pan.y) / scale;
      
      setNodes((prev) =>
        prev.map((n) => (n.id === draggedNode ? { ...n, x, y } : n))
      );
    } else {
      setPan((p) => ({
        x: p.x + e.movementX,
        y: p.y + e.movementY,
      }));
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDraggedNode(null);
  };

  const zoomIn = () => setScale((s) => Math.min(2, s * 1.2));
  const zoomOut = () => setScale((s) => Math.max(0.5, s / 1.2));
  const resetView = () => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  };

  const toggleConnectionMode = () => {
    setConnectionMode(!connectionMode);
    setConnectionFrom(null);
    if (!connectionMode) {
      addNotification({ message: '连线模式已开启，点击两个节点建立连接', type: 'info' });
    }
  };

  const deleteSelected = () => {
    if (selectedNodes.size === 0) {
      addNotification({ message: '请先选择节点', type: 'warning' });
      return;
    }
    setNodes((prev) => prev.filter((n) => !selectedNodes.has(n.id)));
    setSelectedNodes(new Set());
    addNotification({ message: '节点已删除', type: 'success' });
  };

  const selectAll = () => {
    setSelectedNodes(new Set(nodes.map((n) => n.id)));
  };

  const getEdgePath = (edge: GraphEdge) => {
    const from = nodes.find((n) => n.id === edge.source);
    const to = nodes.find((n) => n.id === edge.target);
    if (!from || !to || from.x === undefined || from.y === undefined || to.x === undefined || to.y === undefined) return '';
    
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.sqrt(dx * dx + dy * dy);
    if (length === 0) return '';
    
    const unitX = dx / length;
    const unitY = dy / length;
    
    // Offset for node size
    const offset = 60;
    const startX = from.x + unitX * offset;
    const startY = from.y + unitY * offset;
    const endX = to.x - unitX * offset;
    const endY = to.y - unitY * offset;
    
    return `M ${startX} ${startY} L ${endX} ${endY}`;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[calc(100vh-12rem)]">
        {/* Sidebar */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Share2 className="w-4 h-4 text-primary" />
              控制中心
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" size="sm" className="w-full">
                <MessageCircle className="w-4 h-4 mr-1" />
                聊天
              </Button>
              <Button variant="outline" size="sm" className="w-full">
                <GitBranch className="w-4 h-4 mr-1" />
                规则
              </Button>
              <Button variant="outline" size="sm" className="w-full" onClick={resetView}>
                <Maximize className="w-4 h-4 mr-1" />
                布局
              </Button>
              <Button variant="outline" size="sm" className="w-full" onClick={() => setNodes([])}>
                <Trash2 className="w-4 h-4 mr-1" />
                清空
              </Button>
            </div>

            <div className="border-t border-border pt-4">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
                图例说明
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-3 h-3 rounded-full bg-primary" />
                  <span>聊天节点</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-3 h-3 rounded-full bg-emerald-500" />
                  <span>转发规则</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <ArrowRight className="w-4 h-4 text-primary" />
                  <span>消息流向</span>
                </div>
              </div>
            </div>

            <div className="border-t border-border pt-4">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
                统计指标
              </div>
              <div className="grid grid-cols-2 gap-4 text-center">
                <div className="p-3 rounded-lg bg-muted">
                  <div className="text-2xl font-bold text-primary">{nodes.length}</div>
                  <div className="text-xs text-muted-foreground">节点数</div>
                </div>
                <div className="p-3 rounded-lg bg-muted">
                  <div className="text-2xl font-bold text-emerald-500">{edges.length}</div>
                  <div className="text-xs text-muted-foreground">拓扑连线</div>
                </div>
              </div>
            </div>

            {selectedNodes.size > 0 && (
              <div className="border-t border-border pt-4">
                <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
                  选中节点
                </div>
                <div className="p-3 rounded-lg bg-muted">
                  <div className="text-sm font-medium mb-1">
                    {nodes.find((n) => n.id === Array.from(selectedNodes)[0])?.label}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {nodes.find((n) => n.id === Array.from(selectedNodes)[0])?.type === 'chat'
                      ? '聊天节点'
                      : '转发规则'}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Canvas */}
        <Card className="lg:col-span-3 relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between pb-2 absolute top-0 left-0 right-0 z-10 bg-card/80 backdrop-blur">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Share2 className="w-4 h-4 text-primary" />
              转发拓扑图
              <Badge variant="secondary">BETA</Badge>
            </CardTitle>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={zoomIn}>
                <Plus className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={zoomOut}>
                <Minus className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={resetView}>
                <Maximize className="w-4 h-4" />
              </Button>
            </div>
          </CardHeader>

          {/* Floating Toolbar */}
          <div className="absolute top-20 right-4 z-10 flex flex-col gap-1">
            <Button
              variant={connectionMode ? 'default' : 'secondary'}
              size="icon"
              className="h-9 w-9 shadow-lg"
              onClick={toggleConnectionMode}
            >
              <GitBranch className="w-4 h-4" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              className="h-9 w-9 shadow-lg"
              onClick={selectAll}
            >
              <MousePointer2 className="w-4 h-4" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              className="h-9 w-9 shadow-lg text-red-500"
              onClick={deleteSelected}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>

          <CardContent className="p-0 h-full">
            <div
              ref={canvasRef}
              className="w-full h-full bg-muted/30 relative overflow-hidden cursor-grab active:cursor-grabbing"
              onWheel={handleWheel}
              onMouseDown={(e) => handleMouseDown(e)}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              style={{
                backgroundImage: `
                  radial-gradient(circle at 1px 1px, hsl(var(--border)) 1px, transparent 0)
                `,
                backgroundSize: '20px 20px',
              }}
            >
              <div
                className="absolute inset-0"
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
                  transformOrigin: '0 0',
                }}
              >
                {/* Edges */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                  {edges.map((edge, i) => (
                    <path
                      key={i}
                      d={getEdgePath(edge)}
                      stroke="hsl(var(--primary))"
                      strokeWidth="2"
                      fill="none"
                      opacity={0.4}
                      markerEnd="url(#arrowhead)"
                    />
                  ))}
                  <defs>
                    <marker
                      id="arrowhead"
                      markerWidth="10"
                      markerHeight="7"
                      refX="9"
                      refY="3.5"
                      orient="auto"
                    >
                      <polygon
                        points="0 0, 10 3.5, 0 7"
                        fill="hsl(var(--primary))"
                        opacity={0.4}
                      />
                    </marker>
                  </defs>
                </svg>

                {/* Nodes */}
                {nodes.map((node) => (
                  <div
                    key={node.id}
                    className={`absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all ${
                      selectedNodes.has(node.id)
                        ? 'ring-2 ring-primary ring-offset-2'
                        : ''
                    } ${connectionFrom === node.id ? 'ring-2 ring-amber-500' : ''}`}
                    style={{ left: node.x, top: node.y }}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      handleMouseDown(e, node.id);
                    }}
                  >
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div
                            className={`px-4 py-3 rounded-lg shadow-lg border-2 min-w-[140px] ${
                              node.type === 'chat'
                                ? 'bg-card border-primary'
                                : 'bg-card border-emerald-500'
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              {node.type === 'chat' ? (
                                <MessageCircle className="w-4 h-4 text-primary" />
                              ) : (
                                <GitBranch className="w-4 h-4 text-emerald-500" />
                              )}
                              <span className="font-medium text-sm truncate">{node.label}</span>
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {node.type === 'chat'
                                ? node.data.telegram_chat_id
                                : node.data.enabled
                                ? '运行中'
                                : '已禁用'}
                            </div>
                            {node.type === 'rule' && (
                              <div className="flex gap-1 mt-2">
                                <Badge variant="secondary" className="text-[10px]">
                                  {node.data.keywords_count} 词
                                </Badge>
                              </div>
                            )}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{node.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {node.type === 'chat' ? '聊天节点' : '转发规则'}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
