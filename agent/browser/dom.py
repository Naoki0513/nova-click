from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class ViewportInfo:
    width: int
    height: int

class DOMBaseNode:
    pass

@dataclass
class DOMTextNode(DOMBaseNode):
    text: str
    is_visible: bool
    parent: Optional['DOMElementNode'] = None

@dataclass
class DOMElementNode(DOMBaseNode):
    tag_name: str
    xpath: str
    attributes: Dict[str, Any]
    children: List[DOMBaseNode]
    is_visible: bool
    is_interactive: bool
    is_top_element: bool
    is_in_viewport: bool
    highlight_index: Optional[int]
    shadow_root: bool
    parent: Optional['DOMElementNode'] = None
    viewport_info: Optional[ViewportInfo] = None


def _parse_node(node_data: Dict[str, Any]) -> Tuple[Optional[DOMBaseNode], List[int]]:
    if not node_data:
        return None, []
    if node_data.get('type') == 'TEXT_NODE':
        text_node = DOMTextNode(
            text=node_data.get('text', ''),
            is_visible=node_data.get('isVisible', False),
            parent=None
        )
        return text_node, []
    viewport = None
    if 'viewport' in node_data:
        vp = node_data['viewport']
        viewport = ViewportInfo(width=vp.get('width', 0), height=vp.get('height', 0))
    element_node = DOMElementNode(
        tag_name=node_data.get('tagName', ''),
        xpath=node_data.get('xpath', ''),
        attributes=node_data.get('attributes', {}),
        children=[],
        is_visible=node_data.get('isVisible', False),
        is_interactive=node_data.get('isInteractive', False),
        is_top_element=node_data.get('isTopElement', False),
        is_in_viewport=node_data.get('isInViewport', False),
        highlight_index=node_data.get('highlightIndex'),
        shadow_root=node_data.get('shadowRoot', False),
        parent=None,
        viewport_info=viewport,
    )
    children_ids = node_data.get('children', []) or []
    return element_node, children_ids


def _construct_dom_tree(eval_page: Dict[str, Any]) -> Tuple[Optional[DOMElementNode], Dict[int, DOMElementNode]]:
    js_node_map = eval_page.get('map', {}) or {}
    js_root_id = str(eval_page.get('rootId'))
    selector_map: Dict[int, DOMElementNode] = {}
    node_map: Dict[str, DOMBaseNode] = {}
    for id_str, node_data in js_node_map.items():
        node, children_ids = _parse_node(node_data)
        if node is None:
            continue
        node_map[id_str] = node
        if isinstance(node, DOMElementNode) and node.highlight_index is not None:
            selector_map[node.highlight_index] = node
        if isinstance(node, DOMElementNode):
            for child_id in children_ids:
                child = node_map.get(str(child_id))
                if child:
                    child.parent = node
                    node.children.append(child)
    root_node = node_map.get(js_root_id)
    return root_node, selector_map 