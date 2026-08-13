"""Protocol 分层：多协议共存（当前只实现 F1_25_2026 / 2026 Season Pack）。

- protocol.base：协议无关的基础定义（频率类型、PacketDefinition）。
- protocol.f1_25_2026：2026 Season Pack（packet_format=2026）的 header/registry/parser。
- protocol.f1_25_base：F1 25 本体（packet_format=2025）未来占位，不实现。
"""
