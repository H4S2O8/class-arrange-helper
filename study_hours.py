import json
import pandas as pd

def create_sample_input():
    """创建示例输入文件"""
    sample_input = {
        "自修课安排": {
            "班级7": {
                "周一": {"早自习": "语", "午自习": "数", "晚自习": ""},
                "周二": {"早自习": "英", "午自习": "科", "晚自习": "英"},
                "周三": {"早自习": "语", "午自习": "社", "晚自习": ""},
                "周四": {"早自习": "社", "午自习": "语", "晚自习": "英"},
                "周五": {"早自习": "英", "午自习": "英", "晚自习": "数"}
            },
            "班级8": {
                "周一": {"早自习": "语", "午自习": "英", "晚自习": "科"},
                "周二": {"早自习": "英", "午自习": "语", "晚自习": ""},
                "周三": {"早自习": "语", "午自习": "英", "晚自习": "数"},
                "周四": {"早自习": "社", "午自习": "数", "晚自习": ""},
                "周五": {"早自习": "英", "午自习": "科", "晚自习": "社"}
            }
        }
    }
    
    with open('study_input.json', 'w', encoding='utf-8') as f:
        json.dump(sample_input, f, ensure_ascii=False, indent=2)
    
    print("✅ 已创建示例输入文件 'study_input.json'")
    print("\n📝 输入格式说明:")
    print("- 只需填写自修课安排（早自习、午自习、晚自习）")
    print("- 科目代码: 语、数、英、科、社")
    print("- 空白时段请填写空字符串 \"\"")

def load_study_input(input_file):
    """加载自修课输入"""
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['自修课安排']

def count_weekly_hours_simple(study_schedule, fixed_schedule=None):
    """简化版周课时统计（如果没有正课数据，只统计自修课）"""
    classes = ['班级7', '班级8']
    days = ['周一', '周二', '周三', '周四', '周五']
    subjects = ['语', '数', '英', '科', '社']
    
    # 初始化统计数据
    teacher_stats = {}
    for subject in subjects:
        teacher_stats[subject] = {
            'daily_hours': {day: 0 for day in days},
            'weekly_total': 0,
            'study_hours': 0,  # 自修课课时
            'course_details': {day: [] for day in days}
        }
    
    # 统计自修课
    for day in days:
        for subject in subjects:
            daily_count = 0
            day_details = []
            
            for class_name in classes:
                study_periods = ['早自习', '午自习', '晚自习']
                
                for period in study_periods:
                    if study_schedule.get(class_name, {}).get(day, {}).get(period) == subject:
                        daily_count += 1
                        day_details.append(f"{period}({class_name})")
            
            # 如果有正课数据，也统计正课
            if fixed_schedule:
                for class_name in classes:
                    for i, period_info in enumerate(fixed_schedule[class_name][day]):
                        if period_info['course'] == subject:
                            daily_count += 1
                            period_num = i + 1 if i < 4 else i + 2
                            day_details.append(f"第{period_num}节({class_name}-正课)")
            
            teacher_stats[subject]['daily_hours'][day] = daily_count
            teacher_stats[subject]['weekly_total'] += daily_count
            teacher_stats[subject]['course_details'][day] = day_details
            
            # 统计自修课时数
            if not fixed_schedule:  # 如果没有正课数据，所有课时都是自修课
                teacher_stats[subject]['study_hours'] += daily_count
    
    return teacher_stats

def display_simple_summary(teacher_stats):
    """显示简化的周课时统计"""
    print("\n📊 老师周课时统计:")
    print("=" * 60)
    
    days = ['周一', '周二', '周三', '周四', '周五']
    subjects = ['语', '数', '英', '科', '社']
    
    # 创建统计表格
    summary_data = []
    for subject in subjects:
        stats = teacher_stats[subject]
        row = [f"{subject}学老师"]
        
        # 添加每日课时
        for day in days:
            row.append(stats['daily_hours'][day])
        
        # 添加周总计
        row.append(stats['weekly_total'])
        summary_data.append(row)
    
    columns = ['老师'] + days + ['周总计']
    df = pd.DataFrame(summary_data, columns=columns)
    print(df.to_string(index=False))

def display_study_details(teacher_stats):
    """显示自修课详情"""
    print("\n📋 自修课详细安排:")
    print("=" * 60)
    
    days = ['周一', '周二', '周三', '周四', '周五']
    subjects = ['语', '数', '英', '科', '社']
    
    for subject in subjects:
        stats = teacher_stats[subject]
        print(f"\n{subject}学老师的自修课安排:")
        print("-" * 40)
        
        has_classes = False
        for day in days:
            if stats['course_details'][day]:
                study_classes = [detail for detail in stats['course_details'][day] 
                               if '自习' in detail]
                if study_classes:
                    print(f"  {day}: {', '.join(study_classes)}")
                    has_classes = True
        
        if not has_classes:
            print(f"  无自修课安排")
        
        study_total = sum(1 for day in days for detail in stats['course_details'][day] 
                         if '自习' in detail)
        print(f"  自修课总计: {study_total}节")

def validate_study_schedule(study_schedule):
    """验证自修课安排是否合理"""
    print("\n🔍 自修课安排验证:")
    print("=" * 50)
    
    classes = ['班级7', '班级8']
    days = ['周一', '周二', '周三', '周四', '周五']
    subjects = ['语', '数', '英', '科', '社']
    violations = []
    
    # 检查每个时段是否有冲突
    for day in days:
        for period in ['早自习', '午自习', '晚自习']:
            period_subjects = []
            for class_name in classes:
                subject = study_schedule.get(class_name, {}).get(day, {}).get(period)
                if subject:
                    if subject in period_subjects:
                        violations.append(f"{day}{period}: 两个班级都安排了{subject}")
                    period_subjects.append(subject)
    
    # 检查科目分配是否均匀
    for subject in subjects:
        for period in ['午自习', '晚自习']:
            count = 0
            for class_name in classes:
                for day in days:
                    if study_schedule.get(class_name, {}).get(day, {}).get(period) == subject:
                        count += 1
            if count != 0 and count != 2:  # 要么不安排，要么两个班各1节
                violations.append(f"{period}{subject}: 分配不均匀({count}节)")
    
    if violations:
        print("❌ 发现问题:")
        for violation in violations:
            print(f"   - {violation}")
    else:
        print("✅ 自修课安排验证通过!")

def main():
    """主函数"""
    print("🎯 自修课课时统计工具")
    print("=" * 50)
    
    # 检查是否存在示例文件，如果不存在则创建
    import os
    if not os.path.exists('study_input.json'):
        print("📁 未找到输入文件，正在创建示例...")
        create_sample_input()
        print("\n请编辑 'study_input.json' 文件，填入您的自修课安排后重新运行。")
        return
    
    try:
        # 加载自修课安排
        study_schedule = load_study_input('study_input.json')
        
        # 尝试加载正课数据（可选）
        fixed_schedule = None
        if os.path.exists('classes.json'):
            with open('classes.json', 'r', encoding='utf-8') as f:
                fixed_schedule = json.load(f)
            print("📚 已加载正课数据，将显示完整课时统计")
        else:
            print("📝 仅显示自修课统计（未找到正课数据）")
        
        # 验证自修课安排
        validate_study_schedule(study_schedule)
        
        # 统计课时
        teacher_stats = count_weekly_hours_simple(study_schedule, fixed_schedule)
        
        # 显示结果
        display_simple_summary(teacher_stats)
        display_study_details(teacher_stats)
        
        # 保存结果
        output_data = {
            "自修课安排": study_schedule,
            "课时统计": teacher_stats
        }
        
        with open('study_hours_result.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print("\n💾 结果已保存到 'study_hours_result.json'")
        
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()