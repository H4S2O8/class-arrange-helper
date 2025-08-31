import json
import itertools
from pulp import *
import pandas as pd

class StudySessionScheduler:
    def __init__(self, classes_file):
        """初始化排课系统"""
        with open(classes_file, 'r', encoding='utf-8') as f:
            self.fixed_schedule = json.load(f)
        
        self.classes = ['班级7', '班级8']
        self.days = ['周一', '周二', '周三', '周四', '周五']
        self.subjects = ['语', '数', '英', '科', '社']
        self.study_periods = ['早自习', '午自习', '晚自习']
        
        # 创建决策变量
        self.variables = {}
        self.continuous_vars = {}  # 连续上课的指示变量
        self._create_variables()
        
        # 创建优化问题
        self.prob = LpProblem("StudySession_Schedule", LpMinimize)
        
    def _create_variables(self):
        """创建决策变量：x[班级][天][时段][科目] = 1表示安排该课程"""
        for class_name in self.classes:
            for day in self.days:
                for period in self.study_periods:
                    for subject in self.subjects:
                        var_name = f"{class_name}_{day}_{period}_{subject}"
                        self.variables[var_name] = LpVariable(var_name, cat='Binary')
        
        # 创建连续上课的指示变量
        continuous_periods = [
            [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6],
            [5, 6, 7], [6, 7, 8], [7, 8, 9], [8, 9, 10]
        ]
        
        for day in self.days:
            for subject in self.subjects:
                for i, periods in enumerate(continuous_periods):
                    var_name = f"continuous_{day}_{subject}_{i}"
                    self.continuous_vars[var_name] = LpVariable(var_name, cat='Binary')
    
    def _count_fixed_courses(self, class_name, day, subject):
        """统计某班某天某科目的正课节数"""
        count = 0
        day_schedule = self.fixed_schedule[class_name][day]
        for period_info in day_schedule:
            if period_info['course'] == subject:
                count += 1
        return count
    
    def _is_teacher_teaching(self, day, period_index, subject):
        """检查某个老师在指定时段是否在上课（考虑两个班级）"""
        total_classes = 0
        
        for class_name in self.classes:
            if period_index == 0:  # 早自习
                total_classes += self.variables[f"{class_name}_{day}_早自习_{subject}"]
            elif period_index == 5:  # 午自习
                total_classes += self.variables[f"{class_name}_{day}_午自习_{subject}"]
            elif period_index == 10:  # 晚自习
                total_classes += self.variables[f"{class_name}_{day}_晚自习_{subject}"]
            elif 1 <= period_index <= 4:  # 上午正课
                fixed_index = period_index - 1
                if self.fixed_schedule[class_name][day][fixed_index]['course'] == subject:
                    total_classes += 1
            elif 6 <= period_index <= 9:  # 下午正课
                fixed_index = period_index - 2
                if self.fixed_schedule[class_name][day][fixed_index]['course'] == subject:
                    total_classes += 1
        
        return total_classes

    def add_constraints(self):
        """添加所有约束条件"""
        
        # 约束1: 早自修语文、英语各4节，社会2节，平均分配到两个班级
        for subject, total_sessions in [('语', 4), ('英', 4), ('社', 2)]:
            # 总数约束
            self.prob += lpSum([
                self.variables[f"{class_name}_{day}_早自习_{subject}"]
                for class_name in self.classes
                for day in self.days
            ]) == total_sessions
            
            # 平均分配约束
            for class_name in self.classes:
                expected = total_sessions // 2
                self.prob += lpSum([
                    self.variables[f"{class_name}_{day}_早自习_{subject}"]
                    for day in self.days
                ]) == expected
        
        # 早自修其他科目不安排
        for subject in ['数', '科']:
            self.prob += lpSum([
                self.variables[f"{class_name}_{day}_早自习_{subject}"]
                for class_name in self.classes
                for day in self.days
            ]) == 0
        
        # 约束2: 英语晚自修要求周二周四
        for class_name in self.classes:
            for day in self.days:
                if day not in ['周二', '周四']:
                    self.prob += self.variables[f"{class_name}_{day}_晚自习_英"] == 0
        
        # 约束3: 科学周二不能接晚托，数学周四不能接晚托
        for class_name in self.classes:
            self.prob += self.variables[f"{class_name}_周二_晚自习_科"] == 0
            self.prob += self.variables[f"{class_name}_周四_晚自习_数"] == 0
        
        # 约束4: 午自修/晚自修语、数、英、科、社各2节，平均分配到两个班
        for subject in self.subjects:
            for period in ['午自习', '晚自习']:
                # 总数约束
                self.prob += lpSum([
                    self.variables[f"{class_name}_{day}_{period}_{subject}"]
                    for class_name in self.classes
                    for day in self.days
                ]) == 2
                
                # 平均分配约束
                for class_name in self.classes:
                    self.prob += lpSum([
                        self.variables[f"{class_name}_{day}_{period}_{subject}"]
                        for day in self.days
                    ]) == 1
        
        # 约束5: 每门课程全天总节数不超过4节（每班限制）
        for class_name in self.classes:
            for day in self.days:
                for subject in self.subjects:
                    fixed_count = self._count_fixed_courses(class_name, day, subject)
                    study_sessions = lpSum([
                        self.variables[f"{class_name}_{day}_{period}_{subject}"]
                        for period in self.study_periods
                    ])
                    self.prob += fixed_count + study_sessions <= 4
        
        # 约束5+: 每个老师（科目）一天只能上4节课（两个班的正课+自修课总和）
        for day in self.days:
            for subject in self.subjects:
                total_fixed = sum([
                    self._count_fixed_courses(class_name, day, subject)
                    for class_name in self.classes
                ])
                
                total_study = lpSum([
                    self.variables[f"{class_name}_{day}_{period}_{subject}"]
                    for class_name in self.classes
                    for period in self.study_periods
                ])
                
                self.prob += total_fixed + total_study <= 4
        
        # 软约束: 连续上课的指示变量约束
        continuous_periods = [
            [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6],
            [5, 6, 7], [6, 7, 8], [7, 8, 9], [8, 9, 10]
        ]
        
        for day in self.days:
            for subject in self.subjects:
                for i, periods in enumerate(continuous_periods):
                    # 计算这3个时段该老师的总课时
                    total_in_periods = 0
                    for period_idx in periods:
                        total_in_periods += self._is_teacher_teaching(day, period_idx, subject)
                    
                    # 如果连续3节课都上，则连续指示变量为1
                    continuous_var = self.continuous_vars[f"continuous_{day}_{subject}_{i}"]
                    # total_in_periods >= 3 => continuous_var = 1
                    self.prob += continuous_var >= (total_in_periods - 2) / 1
                    # total_in_periods <= 2 => continuous_var = 0
                    self.prob += continuous_var <= total_in_periods / 3
        
        # 约束6: 社会不能参加周三的晚自习
        for class_name in self.classes:
            self.prob += self.variables[f"{class_name}_周三_晚自习_社"] == 0
        
        # 约束7: 两个班级同一时间段不能上同一门课
        for day in self.days:
            for period in self.study_periods:
                for subject in self.subjects:
                    self.prob += lpSum([
                        self.variables[f"{class_name}_{day}_{period}_{subject}"]
                        for class_name in self.classes
                    ]) <= 1
        
        # 每个时段每个班级只能安排一门课
        for class_name in self.classes:
            for day in self.days:
                for period in self.study_periods:
                    self.prob += lpSum([
                        self.variables[f"{class_name}_{day}_{period}_{subject}"]
                        for subject in self.subjects
                    ]) <= 1
    
    def solve(self):
        """求解优化问题"""
        # 设置目标函数：最小化连续上课次数，优先保护科学老师
        objective = 0
        
        continuous_periods = [
            [0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6],
            [5, 6, 7], [6, 7, 8], [7, 8, 9], [8, 9, 10]
        ]
        
        for day in self.days:
            for subject in self.subjects:
                for i, periods in enumerate(continuous_periods):
                    continuous_var = self.continuous_vars[f"continuous_{day}_{subject}_{i}"]
                    if subject == '科':  # 科学老师优先保护，权重更高
                        objective += 10 * continuous_var
                    else:
                        objective += 1 * continuous_var
        
        self.prob += objective
        
        # 添加约束
        self.add_constraints()
        
        # 求解
        self.prob.solve(PULP_CBC_CMD(msg=0))
        
        if self.prob.status == LpStatusOptimal:
            return self._extract_solution()
        else:
            print(f"求解状态: {LpStatus[self.prob.status]}")
            return None
    
    def _extract_solution(self):
        """提取求解结果"""
        schedule = {}
        
        for class_name in self.classes:
            schedule[class_name] = {}
            for day in self.days:
                schedule[class_name][day] = {
                    '早自习': None,
                    '午自习': None,
                    '晚自习': None
                }
                
                for period in self.study_periods:
                    for subject in self.subjects:
                        var_name = f"{class_name}_{day}_{period}_{subject}"
                        if self.variables[var_name].varValue == 1:
                            schedule[class_name][day][period] = subject
        
        return schedule
    
    def generate_complete_schedule(self, study_schedule):
        """生成完整课表（包含正课和自修课）"""
        complete_schedule = {}
        
        for class_name in self.classes:
            complete_schedule[class_name] = {}
            
            for day in self.days:
                complete_schedule[class_name][day] = []
                
                # 1. 早自习（第0节）
                early_study = study_schedule[class_name][day]['早自习']
                complete_schedule[class_name][day].append({
                    "period": 0,
                    "course": early_study if early_study else "",
                    "type": "早自习"
                })
                
                # 2. 正课第1-4节
                for i in range(4):
                    period_info = self.fixed_schedule[class_name][day][i]
                    complete_schedule[class_name][day].append({
                        "period": i + 1,
                        "course": period_info['course'],
                        "type": "正课"
                    })
                
                # 3. 午自习（第5节）
                noon_study = study_schedule[class_name][day]['午自习']
                complete_schedule[class_name][day].append({
                    "period": 5,
                    "course": noon_study if noon_study else "",
                    "type": "午自习"
                })
                
                # 4. 正课第5-8节（原来的第5-8节变成第6-9节）
                for i in range(4, 8):
                    period_info = self.fixed_schedule[class_name][day][i]
                    complete_schedule[class_name][day].append({
                        "period": i + 2,
                        "course": period_info['course'],
                        "type": "正课"
                    })
                
                # 5. 晚自习（第10节）
                evening_study = study_schedule[class_name][day]['晚自习']
                complete_schedule[class_name][day].append({
                    "period": 10,
                    "course": evening_study if evening_study else "",
                    "type": "晚自习"
                })
        
        return complete_schedule
    
    def display_complete_schedule(self, complete_schedule):
        """显示完整课表"""
        print("\n完整课表（包含正课和自修课）:")
        print("=" * 80)
        
        for class_name in self.classes:
            print(f"\n{class_name}:")
            print("-" * 60)
            
            # 创建完整课表数据
            data = []
            for day in self.days:
                day_courses = []
                for period_info in complete_schedule[class_name][day]:
                    course = period_info['course']
                    course_type = period_info['type']
                    if course_type in ['早自习', '午自习', '晚自习']:
                        if course:
                            day_courses.append(f"{course}({course_type})")
                        else:
                            day_courses.append(f"({course_type})")
                    else:
                        day_courses.append(course)
                
                # 按时间顺序排列：早自习, 1-4节正课, 午自习, 5-8节正课, 晚自习
                row = [day] + day_courses
                data.append(row)
            
            columns = ['日期', '早自习', '第1节', '第2节', '第3节', '第4节', 
                      '午自习', '第5节', '第6节', '第7节', '第8节', '晚自习']
            df = pd.DataFrame(data, columns=columns)
            print(df.to_string(index=False))
    
    def validate_constraints(self, schedule):
        """验证排课结果是否符合所有约束条件"""
        print("\n约束验证结果:")
        print("=" * 60)
        
        violations = []
        
        # 验证约束1: 早自修语文、英语各4节，社会2节，平均分配
        print("1. 验证早自修安排:")
        for subject, expected_total in [('语', 4), ('英', 4), ('社', 2)]:
            total_count = 0
            class_counts = {}
            
            for class_name in self.classes:
                class_count = 0
                for day in self.days:
                    if schedule[class_name][day]['早自习'] == subject:
                        class_count += 1
                        total_count += 1
                class_counts[class_name] = class_count
            
            expected_per_class = expected_total // 2
            print(f"   {subject}文: 总计{total_count}节(要求{expected_total}节), 班级7: {class_counts['班级7']}节, 班级8: {class_counts['班级8']}节(各要求{expected_per_class}节)")
            
            if total_count != expected_total:
                violations.append(f"早自修{subject}文总节数不符合要求")
            if class_counts['班级7'] != expected_per_class or class_counts['班级8'] != expected_per_class:
                violations.append(f"早自修{subject}文班级分配不均匀")
        
        # 验证早自修不安排数学和科学
        for subject in ['数', '科']:
            for class_name in self.classes:
                for day in self.days:
                    if schedule[class_name][day]['早自习'] == subject:
                        violations.append(f"早自修不应安排{subject}学")
        
        # 验证约束2: 英语晚自修要求周二周四
        print("2. 验证英语晚自修时间:")
        english_evening = []
        for class_name in self.classes:
            for day in self.days:
                if schedule[class_name][day]['晚自习'] == '英':
                    english_evening.append(f"{class_name}{day}")
                    if day not in ['周二', '周四']:
                        violations.append(f"英语晚自修安排在非周二周四: {class_name}{day}")
        print(f"   英语晚自修安排: {', '.join(english_evening)}")
        
        # 验证约束3: 科学周二不能接晚托，数学周四不能接晚托
        print("3. 验证特殊晚托限制:")
        for class_name in self.classes:
            if schedule[class_name]['周二']['晚自习'] == '科':
                violations.append(f"科学不能在周二晚托: {class_name}")
            if schedule[class_name]['周四']['晚自习'] == '数':
                violations.append(f"数学不能在周四晚托: {class_name}")
        print("   科学周二晚托和数学周四晚托检查通过")
        
        # 验证约束4: 午自修/晚自修各科目各2节，平均分配
        print("4. 验证午自修和晚自修分配:")
        for period in ['午自习', '晚自习']:
            for subject in self.subjects:
                total_count = 0
                class_counts = {}
                
                for class_name in self.classes:
                    class_count = 0
                    for day in self.days:
                        if schedule[class_name][day][period] == subject:
                            class_count += 1
                            total_count += 1
                    class_counts[class_name] = class_count
                
                print(f"   {period}{subject}: 总计{total_count}节(要求2节), 班级7: {class_counts['班级7']}节, 班级8: {class_counts['班级8']}节(各要求1节)")
                
                if total_count != 2:
                    violations.append(f"{period}{subject}总节数不符合要求")
                if class_counts['班级7'] != 1 or class_counts['班级8'] != 1:
                    violations.append(f"{period}{subject}班级分配不均匀")
        
        # 验证约束5: 每门课程全天总节数不超过4节（每班限制）
        print("5. 验证每班每日总节数限制:")
        for class_name in self.classes:
            for day in self.days:
                day_subjects = {}
                
                # 统计正课
                for period_info in self.fixed_schedule[class_name][day]:
                    subject = period_info['course']
                    day_subjects[subject] = day_subjects.get(subject, 0) + 1
                
                # 统计自修课
                for period in self.study_periods:
                    subject = schedule[class_name][day][period]
                    if subject:
                        day_subjects[subject] = day_subjects.get(subject, 0) + 1
                
                for subject, count in day_subjects.items():
                    if count > 4:
                        violations.append(f"{class_name}{day}{subject}科目总节数超过4节: {count}节")
        print("   每班每日总节数检查通过")
        
        # 验证约束5+: 每个老师一天只能上4节课
        print("5+. 验证老师每日课时限制:")
        for day in self.days:
            for subject in self.subjects:
                # 统计该老师当天的总课时
                total_courses = 0
                
                # 统计两个班的正课
                for class_name in self.classes:
                    total_courses += self._count_fixed_courses(class_name, day, subject)
                
                # 统计两个班的自修课
                for class_name in self.classes:
                    for period in self.study_periods:
                        if schedule[class_name][day][period] == subject:
                            total_courses += 1
                
                print(f"   {day}{subject}老师: {total_courses}节课(限制4节)")
                if total_courses > 4:
                    violations.append(f"{day}{subject}老师课时超过4节: {total_courses}节")
        
        # 验证软约束: 老师连续上课情况统计
        print("5++. 统计老师连续课时情况:")
        continuous_count = 0
        science_continuous = 0
        
        for day in self.days:
            for subject in self.subjects:
                # 构建该老师一天的课程时间表
                teacher_schedule = [0] * 11  # 0-10节课
                
                # 填入课程
                for class_name in self.classes:
                    # 早自习
                    if schedule[class_name][day]['早自习'] == subject:
                        teacher_schedule[0] = 1
                    # 上午正课 1-4节
                    for i in range(4):
                        if self.fixed_schedule[class_name][day][i]['course'] == subject:
                            teacher_schedule[i + 1] = 1
                    # 午自习
                    if schedule[class_name][day]['午自习'] == subject:
                        teacher_schedule[5] = 1
                    # 下午正课 6-9节
                    for i in range(4, 8):
                        if self.fixed_schedule[class_name][day][i]['course'] == subject:
                            teacher_schedule[i + 2] = 1
                    # 晚自习
                    if schedule[class_name][day]['晚自习'] == subject:
                        teacher_schedule[10] = 1
                
                # 检查连续3节课
                for i in range(9):  # 0-8开始的连续3节
                    if sum(teacher_schedule[i:i+3]) >= 3:
                        continuous_count += 1
                        if subject == '科':
                            science_continuous += 1
                        period_names = []
                        for j in range(i, i+3):
                            if j == 0:
                                period_names.append("早自习")
                            elif j == 5:
                                period_names.append("午自习")
                            elif j == 10:
                                period_names.append("晚自习")
                            else:
                                period_names.append(f"第{j}节")
                        print(f"   {day}{subject}老师连续上课: {' -> '.join(period_names)}")
        
        print(f"   总连续上课次数: {continuous_count}, 科学老师连续上课次数: {science_continuous}")
        
        # 验证约束6: 社会不能参加周三的晚自习
        print("6. 验证社会周三晚自习限制:")
        for class_name in self.classes:
            if schedule[class_name]['周三']['晚自习'] == '社':
                violations.append(f"社会不能在周三晚自习: {class_name}")
        print("   社会周三晚自习限制检查通过")
        
        # 验证约束7: 两个班级同一时间段不能上同一门课
        print("7. 验证班级间冲突:")
        conflicts = []
        for day in self.days:
            for period in self.study_periods:
                subjects_in_period = []
                for class_name in self.classes:
                    subject = schedule[class_name][day][period]
                    if subject:
                        if subject in subjects_in_period:
                            conflicts.append(f"{day}{period}: 两个班级都安排了{subject}")
                            violations.append(f"{day}{period}: 班级冲突")
                        subjects_in_period.append(subject)
        
        if conflicts:
            for conflict in conflicts:
                print(f"   冲突: {conflict}")
        else:
            print("   班级间冲突检查通过")
        
        # 输出验证结果
        print("\n" + "=" * 60)
        if violations:
            print("❌ 发现约束违反:")
            for violation in violations:
                print(f"   - {violation}")
            return False
        else:
            print("✅ 所有硬约束条件均满足！排课方案有效。")
            print(f"📊 软约束优化结果: 总连续上课{continuous_count}次，科学老师连续上课{science_continuous}次")
            return True
    
    def display_schedule(self, schedule):
        """显示自修课排课结果"""
        if schedule is None:
            print("无法找到满足所有约束的排课方案")
            return
        
        print("自修课排课结果:")
        print("=" * 60)
        
        for class_name in self.classes:
            print(f"\n{class_name}:")
            print("-" * 40)
            
            # 创建表格显示
            data = []
            for day in self.days:
                row = [day]
                for period in self.study_periods:
                    subject = schedule[class_name][day][period]
                    row.append(subject if subject else "")
                data.append(row)
            
            df = pd.DataFrame(data, columns=['日期', '早自习', '午自习', '晚自习'])
            print(df.to_string(index=False))
    
    def save_schedule(self, schedule, complete_schedule, filename):
        """保存排课结果到JSON文件"""
        if schedule and complete_schedule:
            output_data = {
                "study_schedule": schedule,
                "complete_schedule": complete_schedule
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n排课结果已保存到 {filename}")

    def display_teacher_schedule(self, complete_schedule):
        """显示面向老师的课表"""
        print("\n老师课表（以老师为中心）:")
        print("=" * 80)
        
        # 为每个老师（科目）构建课表
        for subject in self.subjects:
            print(f"\n{subject}学老师:")
            print("-" * 60)
            
            # 创建老师课表数据
            data = []
            for day in self.days:
                day_courses = []
                
                # 检查每个时段
                for period_idx in range(11):  # 0-10节课
                    period_info = self._get_teacher_period_info(complete_schedule, subject, day, period_idx)
                    day_courses.append(period_info)
                
                row = [day] + day_courses
                data.append(row)
            
            columns = ['日期', '早自习', '第1节', '第2节', '第3节', '第4节', 
                    '午自习', '第5节', '第6节', '第7节', '第8节', '晚自习']
            df = pd.DataFrame(data, columns=columns)
            print(df.to_string(index=False))

    def _get_teacher_period_info(self, complete_schedule, subject, day, period_idx):
        """获取老师在指定时段的课程信息"""
        teaching_classes = []
        
        for class_name in self.classes:
            if period_idx < len(complete_schedule[class_name][day]):
                period_info = complete_schedule[class_name][day][period_idx]
                if period_info['course'] == subject:
                    # 根据课程类型添加标识
                    if period_info['type'] == '正课':
                        teaching_classes.append(class_name)
                    else:
                        teaching_classes.append(f"{class_name}({period_info['type']})")
        
        if teaching_classes:
            return ' + '.join(teaching_classes)
        else:
            return ""

    def display_teacher_weekly_summary(self, complete_schedule):
        """显示老师周课时统计"""
        print("\n老师周课时统计:")
        print("=" * 60)
        
        # 创建统计表格
        summary_data = []
        
        for subject in self.subjects:
            # 统计每天的课时
            daily_hours = {}
            weekly_total = 0
            continuous_count = 0
            
            for day in self.days:
                daily_count = 0
                teacher_schedule = [0] * 11  # 0-10节课
                
                # 统计当天课时并构建时间表
                for class_name in self.classes:
                    for period_info in complete_schedule[class_name][day]:
                        if period_info['course'] == subject:
                            daily_count += 1
                            teacher_schedule[period_info['period']] = 1
                
                daily_hours[day] = daily_count
                weekly_total += daily_count
                
                # 检查连续3节课
                for i in range(9):  # 0-8开始的连续3节
                    if sum(teacher_schedule[i:i+3]) >= 3:
                        continuous_count += 1
            
            # 构建行数据
            row = [f"{subject}学老师"]
            for day in self.days:
                row.append(daily_hours[day])
            row.extend([weekly_total, continuous_count])
            summary_data.append(row)
        
        columns = ['老师'] + self.days + ['周总计', '连续3节次数']
        df = pd.DataFrame(summary_data, columns=columns)
        print(df.to_string(index=False))

    def display_teacher_detail_schedule(self, complete_schedule):
        """显示老师详细课程安排"""
        print("\n老师详细课程安排:")
        print("=" * 80)
        
        for subject in self.subjects:
            print(f"\n{subject}学老师的课程详情:")
            print("-" * 50)
            
            total_classes = 0
            for day in self.days:
                day_classes = []
                
                for class_name in self.classes:
                    for period_info in complete_schedule[class_name][day]:
                        if period_info['course'] == subject:
                            period_type = period_info['type']
                            period_num = period_info['period']
                            
                            if period_num == 0:
                                time_desc = "早自习"
                            elif period_num == 5:
                                time_desc = "午自习"
                            elif period_num == 10:
                                time_desc = "晚自习"
                            else:
                                time_desc = f"第{period_num}节"
                            
                            day_classes.append(f"{time_desc}({class_name}-{period_type})")
                            total_classes += 1
                
                if day_classes:
                    print(f"  {day}: {', '.join(day_classes)}")
            
            print(f"  周总课时: {total_classes}节")


# 使用示例
if __name__ == "__main__":
    scheduler = StudySessionScheduler('classes.json')
    study_schedule = scheduler.solve()
    
    if study_schedule:
        # 显示自修课排课结果
        scheduler.display_schedule(study_schedule)
        
        # 验证约束条件
        scheduler.validate_constraints(study_schedule)
        
        # 生成并显示完整课表
        complete_schedule = scheduler.generate_complete_schedule(study_schedule)
        scheduler.display_complete_schedule(complete_schedule)

        # 显示老师课表
        scheduler.display_teacher_schedule(complete_schedule)
        
        # 显示老师周课时统计
        scheduler.display_teacher_weekly_summary(complete_schedule)
        
        # 显示老师详细课程安排
        scheduler.display_teacher_detail_schedule(complete_schedule)
        
        
        # 保存结果
        scheduler.save_schedule(study_schedule, complete_schedule, 'complete_schedule.json')
    else:
        print("无法生成满足约束的排课方案")