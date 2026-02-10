def pytest_itemcollected(item):
    """테스트 함수의 docstring을 테스트 표시명으로 사용한다."""
    # item.obj는 테스트 함수 객체를 가리키는 공식 속성입니다.
    doc = getattr(item.obj, "__doc__", None)

    if doc:
        # ._nodeid 대신 공식적으로 제공되는 .name 속성을 활용하거나
        # 표시 이름만 바꾸고 싶다면 .user_properties 등을 활용할 수 있지만,
        # 꼭 nodeid를 바꿔야 한다면 아래처럼 안전하게 접근합니다.
        new_name = doc.strip()
        item._nodeid = new_name
