"""AI 입력 파이프라인 (API 명세 §6). 박영준 · 김태한 공동 리뷰 영역.

pipeline.parse() 가 진입점이다. LLM(llm.py) → 규칙 파서(rules.py) → 원문 1건 순으로 폴백한다.
"""
