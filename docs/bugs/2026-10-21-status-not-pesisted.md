# 완료 상태가 새로고침 뒤 유지되지 않음

> 검수 절차 시연을 위해 의도적으로 심은 버그. #5에서 해결됨
    - 원인: PATCH/api/tasks/{id}로 보내 저장되지 않음
    
## 재현 순서 ##
1. 카드의 상태를 '완료'로 바꾼다
2. F5로 새로고침한다.

## 기대 결과 ##
카드의 완료 열에 그대로 있음

## 실제 결과 ##
카드가 할 일 열로 돌아가 있음

## 증거

-- 캡처

[새로고침 전]
![alt text](image.png)


[새로고침 후]
![alt text](image-1.png)

-- Network: PATCH /api/tasks/{번호} 요청했을시 보낸 값{status: "IN_PROGRESS", title: "", description: ""} / 돌아온 값 
{
    "detail": [
        {
            "loc": [
                "title"
            ],
            "msg": "Extra inputs are not permitted"
        },
        {
            "loc": [
                "description"
            ],
            "msg": "Extra inputs are not permitted"
        }
    ]
}	

