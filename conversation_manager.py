import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from vertex_ai_client import Content, Part

class ConversationManager:
    """会話履歴の永続化とセッション管理を行うクラス"""
    
    def __init__(self, conversations_dir: str = "conversations"):
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(exist_ok=True)
        self.current_session = "default"
        
    def _get_session_file(self, session_name: str = None) -> Path:
        """セッションファイルのパスを取得"""
        if session_name is None:
            session_name = self.current_session
        return self.conversations_dir / f"{session_name}.json"
    
    def _content_to_dict(self, content: Content) -> Dict[str, Any]:
        """ContentオブジェクトをJSONシリアライザブルな辞書に変換"""
        parts_data = []
        for part in content.parts:
            if hasattr(part, 'text'):
                parts_data.append({"type": "text", "text": part.text})
            else:
                # 他のタイプのpartがあれば対応を追加
                parts_data.append({"type": "unknown", "data": str(part)})
        
        return {
            "role": content.role,
            "parts": parts_data,
            "timestamp": datetime.now().isoformat()
        }
    
    def _dict_to_content(self, data: Dict[str, Any]) -> Content:
        """辞書からContentオブジェクトに変換"""
        parts = []
        for part_data in data["parts"]:
            if part_data["type"] == "text":
                parts.append(Part.from_text(part_data["text"]))
            # 他のタイプが必要になったら追加
        
        return Content(parts=parts, role=data["role"])
    
    def save_conversation(self, conversation_history: List[Content], session_name: str = None) -> bool:
        """会話履歴を保存"""
        try:
            session_file = self._get_session_file(session_name)
            
            # 会話履歴を辞書形式に変換
            conversation_data = {
                "session_name": session_name or self.current_session,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total_messages": len(conversation_history),
                "conversation": [self._content_to_dict(content) for content in conversation_history]
            }
            
            # JSONファイルに保存
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"会話履歴を保存しました: {session_file} ({len(conversation_history)} メッセージ)")
            return True
            
        except Exception as e:
            logging.error(f"会話履歴の保存に失敗: {e}", exc_info=True)
            return False
    
    def load_conversation(self, session_name: str = None) -> List[Content]:
        """会話履歴を読み込み"""
        try:
            session_file = self._get_session_file(session_name)
            
            if not session_file.exists():
                logging.info(f"セッションファイルが存在しません: {session_file}")
                return []
            
            with open(session_file, 'r', encoding='utf-8') as f:
                conversation_data = json.load(f)
            
            # 辞書形式からContentオブジェクトに変換
            conversation_history = []
            for msg_data in conversation_data.get("conversation", []):
                try:
                    content = self._dict_to_content(msg_data)
                    conversation_history.append(content)
                except Exception as convert_err:
                    logging.warning(f"メッセージの変換に失敗: {convert_err}")
                    continue
            
            logging.info(f"会話履歴を読み込みました: {session_file} ({len(conversation_history)} メッセージ)")
            return conversation_history
            
        except Exception as e:
            logging.error(f"会話履歴の読み込みに失敗: {e}", exc_info=True)
            return []
    
    def get_session_list(self) -> List[str]:
        """利用可能なセッション一覧を取得"""
        try:
            session_files = list(self.conversations_dir.glob("*.json"))
            session_names = [f.stem for f in session_files]
            return sorted(session_names)
        except Exception as e:
            logging.error(f"セッション一覧の取得に失敗: {e}")
            return []
    
    def delete_session(self, session_name: str) -> bool:
        """セッションを削除"""
        try:
            session_file = self._get_session_file(session_name)
            if session_file.exists():
                session_file.unlink()
                logging.info(f"セッションを削除しました: {session_name}")
                return True
            return False
        except Exception as e:
            logging.error(f"セッション削除に失敗: {e}")
            return False
    
    def get_session_info(self, session_name: str = None) -> Optional[Dict[str, Any]]:
        """セッション情報を取得"""
        try:
            session_file = self._get_session_file(session_name)
            if not session_file.exists():
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                "session_name": data.get("session_name"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "total_messages": data.get("total_messages", 0),
                "file_size": session_file.stat().st_size
            }
            
        except Exception as e:
            logging.error(f"セッション情報の取得に失敗: {e}")
            return None
    
    def set_current_session(self, session_name: str):
        """現在のセッションを変更"""
        self.current_session = session_name
        logging.info(f"現在のセッションを変更: {session_name}") 